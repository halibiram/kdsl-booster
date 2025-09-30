"""
This module provides the ReportGenerator class, which is responsible for
formatting the results of a DSLAM detection into various output formats,
including human-readable text, JSON, and CSV.
"""
import json
import csv
import io
from datetime import datetime

class ReportGenerator:
    """
    Formats detection results into structured and human-readable reports.
    """

    def __init__(self, detection_result: dict | None):
        """
        Initializes the report generator with the detection result.

        Args:
            detection_result: The final dictionary output from the
                              UniversalDSLAMDetector's identify_vendor method.
        """
        self.result = detection_result
        self.timestamp = datetime.now().isoformat()

    def generate_text_report(self) -> str:
        """
        Generates a human-readable text summary of the detection results.
        """
        if not self.result:
            return "DSLAM Detection Report\n" \
                   "------------------------\n" \
                   f"Timestamp: {self.timestamp}\n" \
                   "Result: No vendor identified.\n"

        report_lines = [
            "DSLAM Detection Report",
            "------------------------",
            f"Timestamp: {self.timestamp}",
            f"Primary Vendor Identified: {self.result.get('primary_vendor', 'N/A')}",
            f"Overall Confidence: {self.result.get('overall_confidence', 0.0)}%",
            "\nContributing Evidence:",
            "----------------------"
        ]

        for evidence in self.result.get('contributing_methods', []):
            line = (
                f"- Method: {evidence.get('method', 'N/A'):<8} | "
                f"Certainty: {evidence.get('certainty', 0):>3}% | "
                f"Data: {evidence.get('raw_data', 'N/A')}"
            )
            report_lines.append(line)

        return "\n".join(report_lines)

    def generate_json_report(self) -> str:
        """
        Generates a structured JSON report of the detection results.
        """
        report_data = {
            "detection_timestamp": self.timestamp,
            "detection_result": self.result
        }
        return json.dumps(report_data, indent=2)

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