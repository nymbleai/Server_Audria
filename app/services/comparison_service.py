import diff_match_patch as dmp_module
import logging

logger = logging.getLogger(__name__)

class ComparisonService:
    def __init__(self):
        self.dmp = dmp_module.diff_match_patch()

    def compare_html(self, html1: str, html2: str) -> str:
        """
        Compares two HTML strings and returns an HTML string with visual differences.

        Args:
            html1: The first HTML string (e.g., the older version).
            html2: The second HTML string (e.g., the newer version).

        Returns:
            An HTML string that highlights the differences.
        """
        try:
            # Compute the difference
            diffs = self.dmp.diff_main(html1, html2)
            self.dmp.diff_cleanupSemantic(diffs)

            # Convert the diff to a pretty HTML representation
            html_diff = self.dmp.diff_prettyHtml(diffs)
            
            # Wrap the diff in a styled HTML document for better presentation
            styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>HTML Comparison</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
        ins {{ background-color: #e6ffed; text-decoration: none; }}
        del {{ background-color: #ffeef0; text-decoration: none; }}
    </style>
</head>
<body>
    <h1>Document Comparison</h1>
    <hr>
    {html_diff}
</body>
</html>
            """
            
            logger.info("Successfully generated HTML diff.")
            return styled_html

        except Exception as e:
            logger.error(f"Failed to generate HTML diff: {e}")
            raise Exception("Could not compare the provided HTML documents.")

    def generate_json_diff(self, text1, text2):
        dmp = dmp_module.diff_match_patch()
        diff = dmp.diff_main(text1 or '', text2 or '')
        dmp.diff_cleanupSemantic(diff)
        result = []
        for op, text in diff:
            if not text.strip():
                continue
            segment_type = {
                0: 'unchanged',
                -1: 'deleted',
                1: 'added'
            }[op]
            # Add spaces around the segment if it doesn't have them
            if not text.startswith(' ') and result and result[-1]['text'][-1] != ' ':
                text = ' ' + text
            if not text.endswith(' '):
                text = text + ' '
            result.append({
                'type': segment_type,
                'text': text
            })
        return result

# Create a singleton instance
comparison_service = ComparisonService() 