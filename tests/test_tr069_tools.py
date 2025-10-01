import pytest
from unittest.mock import MagicMock, patch
import threading
import time
import main
from src.tr069.acs_spoofer import ACSSpoofer
from src.tr069.client_emulator import CpeEmulator
from src.tr069.fuzzer import CwmpFuzzer

@pytest.fixture
def acs_spoofer_instance():
    """Fixture to create and manage an ACSSpoofer instance for testing."""
    spoofer = ACSSpoofer(host='localhost', port=8888)
    spoofer_thread = threading.Thread(target=spoofer.start, daemon=True)
    spoofer_thread.start()
    time.sleep(0.1) # Give the server a moment to start
    yield spoofer
    spoofer.stop()

def test_acs_spoofer_and_cpe_emulator_interaction(acs_spoofer_instance):
    """
    Tests the basic interaction between the ACS spoofer and the CPE emulator.
    """
    # 1. Test basic Inform/InformResponse
    emulator = CpeEmulator(acs_host='localhost', acs_port=8888)
    response = emulator.connect_and_inform()
    assert response is not None
    assert "cwmp:InformResponse" in response

    # 2. Test SetParameterValues command queuing
    param_name = "InternetGatewayDevice.ManagementServer.PeriodicInformInterval"
    param_value = "60"
    acs_spoofer_instance.queue_set_parameter_value(param_name, param_value)

    response = emulator.connect_and_inform()
    assert response is not None
    assert "cwmp:SetParameterValues" in response
    assert param_name in response
    assert param_value in response

def test_fuzzer_instantiation():
    """
    Tests that the CwmpFuzzer can be instantiated without errors.
    """
    try:
        fuzzer = CwmpFuzzer(target_host='127.0.0.1', target_port=12345)
        assert fuzzer is not None
        assert len(fuzzer.fuzz_cases) > 0
    except Exception as e:
        pytest.fail(f"CwmpFuzzer instantiation failed with an exception: {e}")

def test_main_arg_parsing_acs_mode(monkeypatch):
    """
    Tests that the main function correctly parses 'acs' mode arguments.
    """
    mock_run_acs = MagicMock()
    monkeypatch.setattr(main, "run_acs_spoofer", mock_run_acs)

    test_args = ['main.py', 'acs', '--host', '127.0.0.1']
    monkeypatch.setattr('sys.argv', test_args)

    main.main()

    mock_run_acs.assert_called_once()
    args = mock_run_acs.call_args[0][0]
    assert args.mode == 'acs'
    assert args.host == '127.0.0.1'

def test_main_arg_parsing_fuzzer_mode(monkeypatch):
    """
    Tests that the main function correctly parses 'fuzzer' mode arguments.
    """
    mock_run_fuzzer = MagicMock()
    monkeypatch.setattr(main, "run_fuzzer", mock_run_fuzzer)

    test_args = ['main.py', 'fuzzer', '192.168.1.1']
    monkeypatch.setattr('sys.argv', test_args)

    main.main()

    mock_run_fuzzer.assert_called_once()
    args = mock_run_fuzzer.call_args[0][0]
    assert args.mode == 'fuzzer'
    assert args.target_ip == '192.168.1.1'

def test_main_arg_parsing_cpe_emu_mode(monkeypatch):
    """
    Tests that the main function correctly parses 'cpe-emu' mode arguments.
    """
    mock_run_cpe_emu = MagicMock()
    monkeypatch.setattr(main, "run_cpe_emulator", mock_run_cpe_emu)

    test_args = ['main.py', 'cpe-emu', '--port', '9999']
    monkeypatch.setattr('sys.argv', test_args)

    main.main()

    mock_run_cpe_emu.assert_called_once()
    args = mock_run_cpe_emu.call_args[0][0]
    assert args.mode == 'cpe-emu'
    assert args.port == 9999