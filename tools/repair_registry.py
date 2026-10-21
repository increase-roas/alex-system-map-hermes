"""Native adapters register here without importing the coordinator."""
import importlib
import hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from repair_contracts import RepairAdapter, RepairError


class RepairRegistry:
    def __init__(self):
        self.adapters = {}
        self.limitations = []

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
        with ThreadPoolExecutor(max_workers=4) as executor:
            pending = [(adapter, executor.submit(adapter.discover)) for adapter in adapters]
            # Read results in registration order, independent of completion order.
            for adapter, future in pending:
                try:
                    registered = {}
                    for target in future.result():
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
    for name in ('repair_local_adapters', 'repair_native_adapters', 'repair_remote_adapters'):
        module = importlib.import_module(name)
        module.register_adapters(registry)
    return registry
