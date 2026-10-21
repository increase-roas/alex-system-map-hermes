import unittest
from local_file_scope import applicability, adjacent_ids


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.row = {'id': 'entry', 'path': '/fixture/project/CLAUDE.md', 'real_path': '/fixture/project/CLAUDE.md', 'generated': False, 'is_symlink': False, 'generated_sources': []}
        self.owner = {'id': 'owner', 'path': '/fixture/rules.md', 'real_path': '/fixture/rules.md'}
        self.index = {'home': '/fixture', 'files': [self.row, self.owner], 'references': [{'source_id': 'generated', 'target_id': 'entry', 'kind': 'generated_from'}]}

    def test_indexed_literal_import_owner_and_generated_neighbors(self):
        text = '@../rules.md\n@/outside/not-indexed.md\n'
        self.assertEqual(['owner', 'generated'], adjacent_ids(self.index, self.row, text))
        metadata = applicability(self.index, self.row, text)
        self.assertEqual('import wrapper', metadata['role'])
        self.assertIn('/fixture/project', metadata['scope'])
        self.assertIn('not established', metadata['limitations'][0])
        self.assertIn('owner', metadata['limitations'][-1])

    def test_generated_alias_and_actual_mdc_frontmatter(self):
        self.row.update(generated=True, generated_sources=['../rules.md'], path='/fixture/project/rule.mdc')
        metadata = applicability(self.index, self.row, '---\nglobs: "app/**"\nalwaysApply: false\n---\nRules\n')
        self.assertEqual('generated projection', metadata['role'])
        self.assertEqual('MDC header: globs: "app/**"; alwaysApply: false', metadata['activation'])
        self.assertIn('Declared generated sources', metadata['limitations'][-1])
        self.row.update(generated=False, is_symlink=True)
        self.assertEqual('alias', applicability(self.index, self.row, 'body')['role'])


if __name__ == '__main__': unittest.main()
