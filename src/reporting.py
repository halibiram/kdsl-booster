"""
This module provides the ReportGenerator class, which is responsible for
formatting the results of a DSLAM detection into various output formats,
including a comprehensive text profile, JSON, and CSV.
"""
import json
import csv
import io
from datetime import datetime
from src.log_manager import LogManager

class ReportGenerator:
    """
    Formats detection and capability analysis results into structured reports.
    """

    def __init__(self, detection_result: dict | None, log_manager: LogManager | None = None):
        """
        Initializes the report generator with the full result dictionary.
        """
        self.result = detection_result if detection_result else {}
        self.timestamp = datetime.now().isoformat()
        self.capabilities = self.result.get('capability_analysis', {})
        self.log_manager = log_manager

    def _format_section(self, title: str, lines: list[str], indent: str = "  ") -> list[str]:
        """Helper to format a section with a title and indented lines."""
        if not any(line.strip() for line in lines):
            return []
        return [f"├── {title}"] + [f"│   {indent}{line}" for line in lines]

    def _format_vdsl_profiles(self) -> list[str]:
        data = self.capabilities.get('vdsl2_profiles', {})
        profiles = data.get('consolidated_profiles', [])
        return [f"Supported Profiles: {', '.join(profiles) if profiles else 'None'}"]

    def _format_vectoring(self) -> list[str]:
        data = self.capabilities.get('vectoring', {})
        return [
            f"Hardware Support: {'Yes' if data.get('hardware_support') else 'No'}",
            f"Currently Active: {'Yes' if data.get('is_active') else 'No'}"
        ]

    def _format_bonding(self) -> list[str]:
        data = self.capabilities.get('bonding', {})
        standards = data.get('supported_standards', [])
        return [
            f"Standards Supported: {', '.join(standards) if standards else 'None'}",
            f"Currently Active: {'Yes' if data.get('is_active') else 'No'}"
        ]

    def _format_frequency(self) -> list[str]:
        data = self.capabilities.get('frequency', {})
        return [
            f"Maximum Downstream: {data.get('max_downstream_mhz', 'N/A')} MHz",
            f"Maximum Upstream: {data.get('max_upstream_mhz', 'N/A')} MHz",
            f"Active Band Plan: {data.get('band_plan', 'N/A')}"
        ]

    def _format_retransmission(self) -> list[str]:
        data = self.capabilities.get('retransmission', {})
        return [
            f"G.inp Support: {'Yes' if data.get('g_inp_supported') else 'No'}",
            f"Currently Active: {'Yes' if data.get('is_active') else 'No'}"
        ]

    def _format_psd(self) -> list[str]:
        data = self.capabilities.get('psd', {})
        return [
            f"PSD Mask Class: {data.get('psd_mask_class', 'N/A')}"
        ]

    def _format_optimization_analysis(self) -> list[str]:
        data = self.capabilities.get('optimization_analysis', {})
        lines = []
        warnings = data.get('warnings', [])
        recommendations = data.get('recommendations', [])

        if not warnings and not recommendations:
            return ["No issues or recommendations."]

        for warning in warnings:
            lines.append(f"[WARNING] {warning}")
        for rec in recommendations:
            lines.append(f"[RECOMMENDATION] {rec}")

        return lines

    def _format_forensics_status(self) -> list[str]:
        """Formats the forensics status section."""
        if not self.log_manager:
            return ["Secure Logging: Not configured"]

        status = "Enabled" if self.log_manager.secure_logging_enabled else "Disabled"
        cleanup = "Performed" if self.log_manager.secure_logging_enabled else "N/A"

        return [
            f"Secure Logging: {status}",
            f"Log Cleanup: {cleanup}"
        ]

    def generate_text_report(self) -> str:
        """
        Generates a comprehensive, human-readable text profile of the DSLAM.
        """
        if not self.result:
            return "DSLAM Capability Profile: No data available."

        report_lines = ["DSLAM Capability Profile:"]

        # Basic Information
        basic_info = [
            f"Vendor: {self.result.get('primary_vendor', 'N/A')}",
            f"Confidence: {self.result.get('overall_confidence', 0.0)}%"
        ]
        report_lines.extend(self._format_section("Basic Information", basic_info))

        # Capability Sections
        report_lines.extend(self._format_section("VDSL2 Profile Support", self._format_vdsl_profiles()))
        report_lines.extend(self._format_section("Vectoring Capabilities", self._format_vectoring()))
        report_lines.extend(self._format_section("Bonding Capabilities", self._format_bonding()))
        report_lines.extend(self._format_section("Frequency Support", self._format_frequency()))
        report_lines.extend(self._format_section("Retransmission Support", self._format_retransmission()))
        report_lines.extend(self._format_section("PSD Configuration", self._format_psd()))
        report_lines.extend(self._format_section("Optimization Recommendations", self._format_optimization_analysis()))
        report_lines.extend(self._format_section("Forensics Status", self._format_forensics_status()))

        return "\n".join(report_lines)

    def generate_json_report(self) -> str:
        """
        Generates a structured JSON report matching the comprehensive profile.
        """
        if not self.result:
            return json.dumps({"DSLAM Capability Profile": {"error": "No data available."}}, indent=2)

        profile_data = {
            "Basic Information": {
                "Vendor": self.result.get('primary_vendor', 'N/A'),
                "Model": "Unknown", # Placeholder
                "Firmware": "Unknown", # Placeholder
                "Chipset": "Unknown" # Placeholder
            },
            "VDSL2 Profile Support": {
                "Supported Profiles": self.capabilities.get('vdsl2_profiles', {}).get('consolidated_profiles', []),
                "Currently Active Profile": "Unknown", # Placeholder
            },
            "Vectoring Capabilities": {
                "Hardware Support": self.capabilities.get('vectoring', {}).get('hardware_support', False),
                "Currently Active": self.capabilities.get('vectoring', {}).get('is_active', False),
            },
            "Bonding Capabilities": {
                "Standards Supported": self.capabilities.get('bonding', {}).get('supported_standards', []),
                "Currently Bonded": self.capabilities.get('bonding', {}).get('is_active', False),
            },
            "Frequency Support": {
                "Maximum Downstream": self.capabilities.get('frequency', {}).get('max_downstream_mhz'),
                "Maximum Upstream": self.capabilities.get('frequency', {}).get('max_upstream_mhz'),
                "Active Band Plan": self.capabilities.get('frequency', {}).get('band_plan'),
            },
            "Retransmission Support": {
                "G.inp Support": self.capabilities.get('retransmission', {}).get('g_inp_supported', False),
                "Currently Active": self.capabilities.get('retransmission', {}).get('is_active', False),
            },
            "PSD Configuration": {
                "Downstream PSD Mask": self.capabilities.get('psd', {}).get('psd_mask_class', 'N/A'),
            },
            "Optimization Recommendations": self.capabilities.get('optimization_analysis', {
                "warnings": [],
                "recommendations": []
            }),
            "Forensics Status": {
                "Secure Logging Enabled": self.log_manager.secure_logging_enabled if self.log_manager else False,
                "Log Cleanup Performed": self.log_manager.secure_logging_enabled if self.log_manager else False,
            }
        }

        full_report = {
            "DSLAM Capability Profile": profile_data,
            "_metadata": {
                "timestamp": self.timestamp,
                "raw_detection_result": self.result
            }
        }
        return json.dumps(full_report, indent=2)

    def generate_csv_report(self) -> str:
        """
        Generates a single-row CSV report of the detection results.
        """
        output = io.StringIO()
        # Define headers that can handle both success and failure cases
        headers = [
            "timestamp", "primary_vendor", "overall_confidence",
            "evidence_count", "contributing_methods_summary"
        ]
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        if not self.result:
            writer.writerow({
                "timestamp": self.timestamp,
                "primary_vendor": "N/A",
                "overall_confidence": 0.0,
                "evidence_count": 0,
                "contributing_methods_summary": ""
            })
        else:
            methods = self.result.get('contributing_methods', [])
            summary = "|".join([
                f"{ev.get('method')}:{ev.get('raw_data')}" for ev in methods
            ])
            writer.writerow({
                "timestamp": self.timestamp,
                "primary_vendor": self.result.get('primary_vendor', 'N/A'),
                "overall_confidence": self.result.get('overall_confidence', 0.0),
                "evidence_count": len(methods),
                "contributing_methods_summary": summary
            })

        return output.getvalue()