"""Native adapters register here without importing the coordinator."""
import importlib
import hashlib
from datetime import datetime, timezone
import json
import multiprocessing
from multiprocessing.connection import wait
import os
import signal
import time
from repair_contracts import RepairAdapter, RepairError


def _discover_child(adapter, sender):
    # Each adapter and its subprocesses are cancellable together. Return only
    # safe public inventory, never adapter caches, clients or credentials.
    os.setsid()
    try:
        sender.send_bytes(json.dumps({'targets': adapter.discover()}).encode())
    except BaseException:
        try:
            sender.send_bytes(b'{"unavailable":true}')
        except (OSError, BrokenPipeError):
            pass
    finally:
        sender.close()


def _reap_discovery(process, terminate=False):
    # A native subprocess can outlive its adapter. Kill the whole session even
    # when the session leader exited, then reap our child before returning.
    process.join(timeout=0 if terminate else .1)
    if not terminate and not process.is_alive():
        process.close()
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Darwin can report EPERM for an empty zombie-led group until
            # waitpid reaps its leader. A living child's denial is not ignored.
            process.join(timeout=.1)
            if process.is_alive():
                raise
        process.join(timeout=.1)
    if process.is_alive():
        process.kill()
    process.join()
    process.close()


class RepairRegistry:
    def __init__(self, discovery_timeout=40.0):
        self.adapters = {}
        self.limitations = []
        self.discovery_timeout = discovery_timeout

    def register(self, adapter: RepairAdapter):
        if adapter.adapter_id in self.adapters:
            raise RepairError('duplicate_adapter')
        self.adapters[adapter.adapter_id] = adapter

    def adapter(self, adapter_id):
        if adapter_id not in self.adapters:
            raise RepairError('adapter_unavailable')
        return self.adapters[adapter_id]

    def discover(self):
        targets = {}
        self.limitations = []
        adapters = list(self.adapters.values())
        # POSIX fork keeps native adapter construction local without copying
        # private caches back into the parent. LocalAdapter.registered and the
        # provider readers rehydrate their own caches when a source is opened.
        context = multiprocessing.get_context('fork')
        deadline = time.monotonic() + self.discovery_timeout
        active = {}
        results = {}
        next_index = 0
        try:
            while next_index < len(adapters) or active:
                while next_index < len(adapters) and len(active) < 4 and time.monotonic() < deadline:
                    receiver, sender = context.Pipe(duplex=False)
                    process = context.Process(target=_discover_child, args=(adapters[next_index], sender))
                    process.start()
                    sender.close()
                    active[receiver] = (next_index, process)
                    next_index += 1
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not active:
                    break
                for receiver in wait(list(active), timeout=remaining):
                    index, process = active.pop(receiver)
                    try:
                        result = json.loads(receiver.recv_bytes(maxlength=2 * 1024 * 1024))
                        if isinstance(result, dict) and isinstance(result.get('targets'), list):
                            results[index] = result['targets']
                    except (OSError, EOFError, ValueError):
                        pass
                    finally:
                        receiver.close()
                        _reap_discovery(process)
        finally:
            for receiver, (_, process) in active.items():
                receiver.close()
                _reap_discovery(process, terminate=True)
        # Registration order stays stable regardless of completion order.
        for index, adapter in enumerate(adapters):
            try:
                if index not in results:
                    raise RepairError('discovery_unavailable')
                registered = {}
                for target in results[index]:
                    if target['id'] in targets or target['id'] in registered or target['adapter_id'] != adapter.adapter_id:
                        raise RepairError('invalid_target_registration')
                    registered[target['id']] = target
                targets.update(registered)
            except Exception:
                # One absent native route must not hide the remaining systems.
                # Exception text is never public, even when the provider supplies it.
                identifier = hashlib.sha256(('unavailable:' + adapter.adapter_id).encode()).hexdigest()[:32]
                category = getattr(adapter, 'category', None) or ('remote_files' if adapter.adapter_id.startswith('remote_file_') else adapter.adapter_id.removeprefix('provider_'))
                targets[identifier] = {
                    'id': identifier, 'adapter_id': adapter.adapter_id, 'category': category,
                    'owner': adapter.adapter_id, 'scope': 'remote' if adapter.adapter_id.startswith(('provider_', 'remote_file_')) else 'local',
                    'identity': {'adapter_id': adapter.adapter_id}, 'capabilities': [],
                    'observed_at': datetime.now(timezone.utc).isoformat(), 'evidence': [],
                    'missing_capability': 'discovery_unavailable',
                    'limitations': ['Native discovery unavailable; no repair target was established.'],
                }
                self.limitations.append(adapter.adapter_id + ': discovery_unavailable')
        return targets


def default_registry():
    registry = RepairRegistry()
    for name in ('repair_local_adapters', 'repair_native_adapters', 'repair_remote_adapters', 'repair_plugin_adapters'):
        module = importlib.import_module(name)
        module.register_adapters(registry)
    return registry
