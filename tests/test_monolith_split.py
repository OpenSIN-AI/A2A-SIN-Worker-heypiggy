import pytest
class TestExtractedModules:
    def test_heypiggy_check(self):
        from worker.modules.heypiggy_check import is_login_page, is_dashboard, extract_survey_count
        assert is_login_page("Bitte einloggen mit Ihrer Email")
        assert is_dashboard("Deine verfügbaren Erhebungen: 3")
        assert extract_survey_count("5 verfügbare Umfragen") == 5
    def test_survey_loop(self):
        from worker.modules.survey_loop import SurveyState
        s = SurveyState(url="https://test.com")
        s.record_step("click", element=7); s.add_eur(0.50)
        assert s.steps == 1 and s.eur_earned == 0.50
    def test_answer_strategy(self):
        from worker.modules.answer_strategy import Persona, select_answer
        assert select_answer(Persona.OPTIMISTIC, ["a","b","c"]) == 2
        assert select_answer(Persona.CRITICAL, ["a","b","c"]) == 0
    def test_rewards(self):
        from worker.modules.rewards import extract_eur
        assert extract_eur("Verdienst: 1.71 €") == 1.71
        assert extract_eur("You earned EUR=0.50") == 0.50
    def test_state_machine(self):
        from worker.modules.state_machine import SurveyPhase
        assert SurveyPhase.INIT in SurveyPhase
    def test_recovery_pool(self):
        from worker.modules.recovery_pool import get_strategy
        assert get_strategy(0) == "recapture"
    def test_trap_detector(self):
        from worker.modules.trap_detector import detect_trap, is_honeypot
        assert detect_trap("display:none"); assert is_honeypot("email")
