"""Default context compatibility check; authored input, not model benchmarking."""
import unittest
import test_quality_integration as contracts

class DefaultBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.http=contracts.OllamaFixture()
    @classmethod
    def tearDownClass(cls):cls.http.close()
    setUp=contracts.IntegrationContracts.setUp
    tearDown=contracts.IntegrationContracts.tearDown
    review=contracts.IntegrationContracts.review
    def test_default_8192_context_handles_short_menu_review(self):
        self.cfg={'num_ctx':8192,'num_predict':1536}
        _,r=self.review()
        self.assertEqual(r.total,100)
