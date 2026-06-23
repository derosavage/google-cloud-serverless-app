import unittest
from src.ocr import process_document

class TestOCR(unittest.TestCase):
    
    def test_text_file_processing(self):
        # Sample text containing keywords like 'invoice', 'financial', and 'urgent'
        content = (
            b"This is an invoice document.\n"
            b"We need to discuss financial planning and urgent matters."
        )
        
        metadata = process_document(
            bucket_name="test-bucket",
            file_name="my_invoice.txt",
            file_size=len(content),
            content_type="text/plain",
            file_content=content
        )
        
        self.assertEqual(metadata["filename"], "my_invoice.txt")
        self.assertEqual(metadata["bucket"], "test-bucket")
        self.assertEqual(metadata["size"], len(content))
        self.assertEqual(metadata["content_type"], "text/plain")
        
        # Word count validation
        # Words: This (1) is (2) an (3) invoice (4) document (5) We (6) need (7) to (8) discuss (9) financial (10) planning (11) and (12) urgent (13) matters (14)
        self.assertEqual(metadata["word_count"], 14)
        
        # Tags validation (invoice -> invoice, financial -> financial, urgent/important -> urgent, text-format)
        self.assertIn("invoice", metadata["tags"])
        self.assertIn("financial", metadata["tags"])
        self.assertIn("urgent", metadata["tags"])
        self.assertIn("text-format", metadata["tags"])

    def test_binary_file_processing(self):
        # Binary content
        content = b"\x00\x01\x02\x03\x04"
        
        metadata = process_document(
            bucket_name="test-bucket",
            file_name="scanned_image.png",
            file_size=len(content),
            content_type="image/png",
            file_content=content
        )
        
        self.assertEqual(metadata["filename"], "scanned_image.png")
        self.assertEqual(metadata["content_type"], "image/png")
        
        # Binary file mock verification
        self.assertTrue(50 <= metadata["word_count"] <= 800)
        self.assertIn("mock-ocr", metadata["tags"])
        self.assertIn("png-format", metadata["tags"])
        self.assertTrue(metadata["ocr_text_preview"].startswith("[Simulated OCR Preview"))

    def test_empty_tags_gets_general(self):
        content = b"Hello world."
        
        metadata = process_document(
            bucket_name="test-bucket",
            file_name="simple.txt",
            file_size=len(content),
            content_type="text/plain",
            file_content=content
        )
        
        # Should have text-format and general since no keywords matched
        self.assertIn("text-format", metadata["tags"])
        self.assertIn("general", metadata["tags"])

if __name__ == "__main__":
    unittest.main()
