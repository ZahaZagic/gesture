from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import time
import os

class ReportExporter:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def generate_report(self, metrics, screenshot_path=None):
        """
        Generates a PDF report with the current metrics.
        """
        filename = f"posture_report_{int(time.time())}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        w, h = letter
        
        # Header
        c.setFont("Helvetica-Bold", 24)
        c.drawString(50, h - 50, "Posture Assessment Report")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, h - 80, f"Date: {time.ctime()}")
        
        # Metrics Table
        y = h - 150
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Metrics:")
        y -= 30
        
        c.setFont("Helvetica", 12)
        for key, value in metrics.items():
            line = f"{key.replace('_', ' ').title()}: {value:.2f}"
            c.drawString(70, y, line)
            y -= 25
            
        # Screenshot
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                # Draw image (x, y, width, height)
                # Aspect ratio preservation usually needed, simplistic here
                c.drawImage(screenshot_path, 50, y - 300, width=400, height=300)
                y -= 320
            except Exception as e:
                c.drawString(50, y, f"Could not load screenshot: {e}")
        
        # Conclusion
        y -= 50
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Recommendation:")
        c.setFont("Helvetica", 12)
        c.drawString(50, y - 25, "Please consult a professional physiotherapist for detailed analysis.")
        
        c.save()
        print(f"Report saved to {filepath}")
        return filepath
