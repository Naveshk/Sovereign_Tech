import tempfile
import unittest
from pathlib import Path

from app.services.file_tools.excel_tools import generate_excel_from_records, inspect_excel
from app.services.file_tools.document_generators import markdown_to_pdf
from app.services.file_generator import generate_docx
from app.services.file_tools.ppt_tools import generate_pptx, analyze_pptx
from app.services.file_tools.validation_tools import validate_generated_file


class FileToolTests(unittest.TestCase):
    def test_excel_structured_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.xlsx"
            result = generate_excel_from_records(
                str(p),
                [{"Equipment": "P-101", "Pressure": 12.5, "Status": "OK"},
                 {"Equipment": "V-201", "Pressure": 9.2, "Status": "Open"}],
                title="Engineering Report",
            )
            self.assertEqual(result["records_count"], 2)
            self.assertEqual(result["columns"], ["Equipment", "Pressure", "Status"])
            self.assertEqual(inspect_excel(str(p))["sheets"][0]["rows"], 3)
            validate_generated_file(str(p), "xlsx")

    def test_docx_pdf_pptx_generation(self):
        content = "# Report\n\n## Findings\n- Pump is OK\n\n| Tag | Value |\n|---|---|\n| P-1 | 10 |"
        with tempfile.TemporaryDirectory() as d:
            # DOCX/PDF legacy generators use the project's controlled generated directory.
            docx = generate_docx(content, "Test Report")
            pdf = markdown_to_pdf(content, "Test PDF")
            ppt = generate_pptx(str(Path(d) / "test.pptx"), "Test PPT", "# Summary\n- Pump OK")
            self.assertTrue(Path(docx["file_path"]).is_file())
            self.assertTrue(Path(pdf["file_path"]).is_file())
            self.assertTrue(Path(ppt["file_path"]).is_file())
            self.assertEqual(analyze_pptx(ppt["file_path"])["slide_count"], 2)
            validate_generated_file(docx["file_path"], "docx")
            validate_generated_file(pdf["file_path"], "pdf")
            validate_generated_file(ppt["file_path"], "pptx")


if __name__ == "__main__":
    unittest.main()
