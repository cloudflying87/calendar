from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from django.core.files.base import ContentFile
from django.conf import settings
import calendar as cal
import os
import tempfile
from datetime import datetime
from pypdf import PdfReader, PdfWriter
from PIL import Image
import io


class CalendarPDFGenerator:
    def __init__(self, calendar_obj):
        self.calendar = calendar_obj
        self.year = calendar_obj.year
        self.styles = getSampleStyleSheet()
        self.setup_styles()

    def setup_styles(self):
        """Setup custom styles for the calendar"""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontSize=32,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Times-Bold',
            textColor=colors.HexColor('#1e293b')
        )

        self.month_style = ParagraphStyle(
            'MonthTitle',
            parent=self.styles['Heading1'],
            fontSize=36,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Times-Bold',
            textColor=colors.black,
            leading=40
        )

        self.day_style = ParagraphStyle(
            'DayStyle',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )

    def generate_calendar_only(self):
        """Generate calendar PDF with just the calendar pages"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            doc = SimpleDocTemplate(
                tmp_file.name,
                pagesize=landscape(letter),
                rightMargin=18,  # 0.25 inch margins (18 points = 0.25 inch)
                leftMargin=18,
                topMargin=18,
                bottomMargin=18
            )

            story = []

            # Generate each month (no title page)
            for month_num in range(1, 13):
                month_content = self.generate_month_content(month_num)
                story.extend(month_content)
                # Add page break after each month except the last
                if month_num < 12:
                    from reportlab.platypus import PageBreak
                    story.append(PageBreak())

            doc.build(story)

            # Create Django file object
            with open(tmp_file.name, 'rb') as f:
                content = f.read()

            os.unlink(tmp_file.name)

            # Clean up temporary image files
            self.cleanup_temp_files()

            filename = f"calendar_{self.year}_only.pdf"
            return ContentFile(content, name=filename)

    def generate_month_content(self, month_num):
        """Generate content for a single month"""
        content = []

        # Month title - show month name and year
        month_name = cal.month_name[month_num]
        month_title = Paragraph(f"{month_name} {self.year}", self.month_style)
        content.append(month_title)

        # Calculate number of weeks for dynamic sizing
        cal_obj = cal.monthcalendar(self.year, month_num)
        self.current_month_weeks = len(cal_obj)  # Store for use in create_day_cell

        # Get events for this month
        events = self.calendar.events.filter(month=month_num)
        # Group events by day to handle multiple events
        from collections import defaultdict
        events_dict = defaultdict(list)
        for event in events:
            events_dict[event.day].append(event)

        # Create calendar grid starting with Sunday
        cal.setfirstweekday(6)  # 6 = Sunday as first day
        cal_obj = cal.monthcalendar(self.year, month_num)

        # Prepare table data
        table_data = []

        # Days of week header - starting with Sunday
        days_header = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
        table_data.append(days_header)

        # Calendar days
        for week in cal_obj:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append('')
                else:
                    cell_content = self.create_day_cell(day, events_dict.get(day))
                    week_data.append(cell_content)
            table_data.append(week_data)

        # Create and style the table - maximize size to fill page
        # With 0.25" margins, we have 11" - 0.5" = 10.5" width and 8.5" - 0.5" = 8" height
        # Reserve about 0.5" for month title, leaving 7.5" for calendar
        col_width = 1.48*inch  # ~10.5" / 7 columns
        header_height = 0.3*inch

        # Dynamically adjust row height based on number of weeks
        num_weeks = len(cal_obj)
        # Adjust heights based on number of weeks: 1.65" for 4 weeks, 1.3" for 5 weeks, 1.1" for 6 weeks
        if num_weeks == 4:
            row_height = 1.65*inch
        elif num_weeks == 6:
            row_height = 1.1*inch
        else:  # 5 weeks
            row_height = 1.3*inch

        table = Table(table_data, colWidths=[col_width]*7, rowHeights=[header_height] + [row_height]*num_weeks)

        table_style = TableStyle([
            # Header row - modern styling with white background and bold borders
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),  # Vertically center header
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),

            # Bold top and bottom borders for header
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.black),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),

            # Calendar body - white background with grid
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            # Grid for calendar cells (not header) - slightly darker gray
            ('GRID', (0, 1), (-1, -1), 0.75, colors.HexColor('#9ca3af')),
            # No bold bottom border
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ])

        table.setStyle(table_style)
        content.append(table)
        # Remove spacer to ensure each month fits on one page

        return content

    def get_optimal_font_size(self, text, max_width_chars):
        """Calculate optimal font size based on text length"""
        text_length = len(text)
        # Smaller base sizes for 6-week months
        num_weeks = getattr(self, 'current_month_weeks', 5)
        if num_weeks == 6:
            if text_length <= max_width_chars:
                return 8
            elif text_length <= max_width_chars * 1.5:
                return 7
            else:
                return 6
        else:
            if text_length <= max_width_chars:
                return 10
            elif text_length <= max_width_chars * 1.5:
                return 9
            else:
                return 8

    def create_day_cell(self, day, events_list):
        """Create content for a day cell - now handles multiple events"""
        from reportlab.platypus import Table as CellTable
        from .models import CalendarEvent

        # Handle empty days
        if not events_list or len(events_list) == 0:
            # Simple day number in top left with modern styling
            day_style_left = ParagraphStyle(
                'DayStyleLeft',
                parent=self.styles['Normal'],
                fontSize=16,
                alignment=TA_LEFT,
                fontName='Times-Bold',
                textColor=colors.HexColor('#1f2937')
            )
            return Paragraph(str(day), day_style_left)

        # Create a mini table for the cell content with overlapping layout
        cell_data = []
        combined_img_path = None  # Track for cleanup
        is_combined = False

        # Handle multiple events
        if len(events_list) > 1:
            # Get user's image combination preference
            from .models import UserEventPreferences
            try:
                preferences = UserEventPreferences.objects.get(user=self.calendar.user)
                layout_preference = preferences.image_combination_layout
            except UserEventPreferences.DoesNotExist:
                layout_preference = 'auto'

            # Create combined image for multiple events
            combined_img_path = CalendarEvent.create_combined_image(
                self.calendar, events_list[0].month, day, layout_preference=layout_preference
            )

            # Use combined image if created, otherwise use first event's image
            if combined_img_path:
                event = events_list[0]  # For metadata
                event_image_path = combined_img_path
                is_combined = True
            else:
                # Fall back to first event with image
                event = next((e for e in events_list if e.image), events_list[0])
                event_image_path = event.image.path if event.image else None
                is_combined = False
        else:
            # Single event
            event = events_list[0]
            event_image_path = event.image.path if event.image else None
            is_combined = False

        # Add image first (as background)
        if event_image_path:
            try:
                img_path = event_image_path
                if os.path.exists(img_path):
                    # Process image for PDF
                    with Image.open(img_path) as img:
                        # Convert to RGB if necessary
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')

                        # Dynamically size images based on number of weeks - higher resolution for better quality
                        num_weeks = getattr(self, 'current_month_weeks', 5)
                        if num_weeks == 4:
                            # Larger images for 4-week months - higher res
                            img.thumbnail((200, 150), Image.Resampling.LANCZOS)  # Process at higher res
                            img_width, img_height = 105, 80  # Display at original size
                        elif num_weeks == 6:
                            # Smaller images for 6-week months - higher res
                            img.thumbnail((150, 110), Image.Resampling.LANCZOS)  # Process at higher res
                            img_width, img_height = 80, 60  # Display at original size
                        else:  # 5 weeks
                            # Medium images for 5-week months - higher res
                            img.thumbnail((180, 130), Image.Resampling.LANCZOS)  # Process at higher res
                            img_width, img_height = 95, 70  # Display at original size

                        # Save to temporary file with maximum quality
                        temp_img_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                        img.save(temp_img_file.name, 'JPEG', quality=100, optimize=True, dpi=(300, 300))

                        # Create ReportLab image
                        rl_img = RLImage(temp_img_file.name, width=img_width, height=img_height)

                        # Create day number with white background box overlay - no border, small box
                        day_overlay_style = ParagraphStyle(
                            'DayOverlay',
                            parent=self.styles['Normal'],
                            fontSize=16,
                            alignment=TA_CENTER,
                            fontName='Times-Bold',
                            textColor=colors.HexColor('#1f2937')
                        )

                        # Create overlay table with image and small white box for day number
                        overlay_data = [
                            [rl_img],  # Image as background row
                            [Paragraph(f'<para alignment="center" backColor="white" borderPadding="7">{day}</para>', day_overlay_style)]  # Day number overlay, no border
                        ]

                        # Position small white box right in top-left corner
                        overlay_table = CellTable(overlay_data, colWidths=[1.4*inch], rowHeights=[img_height, 0.01*inch])
                        overlay_table.setStyle(TableStyle([
                            # Image cell (0, 0) styling
                            ('ALIGN', (0, 0), (0, 0), 'CENTER'),  # Center image
                            ('VALIGN', (0, 0), (0, 0), 'TOP'),    # Align image to top
                            ('LEFTPADDING', (0, 0), (0, 0), 0),   # No left padding for image
                            ('RIGHTPADDING', (0, 0), (0, 0), 0),  # No right padding for image
                            ('TOPPADDING', (0, 0), (0, 0), 0),    # No top padding for image
                            ('BOTTOMPADDING', (0, 0), (0, 0), 0), # No bottom padding for image

                            # Day number overlay cell (0, 1) styling
                            ('ALIGN', (0, 1), (0, 1), 'LEFT'),    # Position day number box on left
                            ('VALIGN', (0, 1), (0, 1), 'TOP'),    # Align day number to top
                            ('LEFTPADDING', (0, 1), (0, 1), 2),   # Small left padding for day number
                            ('RIGHTPADDING', (0, 1), (0, 1), 81), # Large right padding to keep box small
                            ('TOPPADDING', (0, 1), (0, 1), -img_height-4),  # Negative padding to overlay on image
                            ('BOTTOMPADDING', (0, 1), (0, 1), img_height), # Keep day number box small
                        ]))

                        cell_data.append([overlay_table])

                        # Store temp file name for cleanup
                        if not hasattr(self, '_temp_files'):
                            self._temp_files = []
                        self._temp_files.append(temp_img_file.name)

                        # Also store combined image temp file if it exists
                        if is_combined and combined_img_path:
                            self._temp_files.append(combined_img_path)
                else:
                    # Image not found, add day number normally then placeholder
                    day_style = ParagraphStyle(
                        'DayStyleLeft',
                        parent=self.styles['Normal'],
                        fontSize=16,
                        alignment=TA_LEFT,
                        fontName='Times-Bold',
                        textColor=colors.HexColor('#1f2937')
                    )
                    cell_data.append([Paragraph(str(day), day_style)])

                    img_style = ParagraphStyle(
                        'ImagePlaceholder',
                        parent=self.styles['Normal'],
                        fontSize=8,
                        alignment=TA_CENTER
                    )
                    cell_data.append([Paragraph("📷 Image", img_style)])
            except Exception:
                # Error processing image, add day number normally then error placeholder
                day_style = ParagraphStyle(
                    'DayStyleLeft',
                    parent=self.styles['Normal'],
                    fontSize=16,
                    alignment=TA_LEFT,
                    fontName='Times-Bold',
                    textColor=colors.HexColor('#1f2937')
                )
                cell_data.append([Paragraph(str(day), day_style)])

                img_style = ParagraphStyle(
                    'ImagePlaceholder',
                    parent=self.styles['Normal'],
                    fontSize=8,
                    alignment=TA_CENTER
                )
                cell_data.append([Paragraph("📷 Error", img_style)])
        else:
            # No image, just add day number at top
            day_style = ParagraphStyle(
                'DayStyleLeft',
                parent=self.styles['Normal'],
                fontSize=16,
                alignment=TA_LEFT,
                fontName='Times-Bold',
                textColor=colors.HexColor('#1f2937')
            )
            cell_data.append([Paragraph(str(day), day_style)])

        # Add event name with wrapping and dynamic sizing
        if events_list:
            # Get combined display name for multiple events
            if len(events_list) > 1:
                display_name = CalendarEvent.get_combined_display_name(
                    self.calendar, events_list[0].month, day
                )
            else:
                display_name = event.get_display_name()
            optimal_font_size = self.get_optimal_font_size(display_name, 15)

            # Make font smaller for 6-week months
            num_weeks = getattr(self, 'current_month_weeks', 5)
            if num_weeks == 6:
                font_size = optimal_font_size  # No +2 for 6-week months
                leading = optimal_font_size + 1  # Tighter line spacing
            else:
                font_size = optimal_font_size + 2  # Normal sizing for 4-5 week months
                leading = optimal_font_size + 3

            event_style = ParagraphStyle(
                'EventStyle',
                parent=self.styles['Normal'],
                fontSize=font_size,
                alignment=TA_CENTER,
                fontName='Helvetica-Oblique',  # Italic for event names
                leading=leading,  # Adjusted line spacing
                textColor=colors.HexColor('#374151'),
                wordWrap='LTR'  # Enable word wrapping
            )
            # No truncation - let it wrap
            cell_data.append([Paragraph(display_name, event_style)])

        # Create mini table for this cell - larger to fill space
        mini_table = CellTable(cell_data, colWidths=[1.4*inch])

        # Dynamically adjust row heights based on number of weeks in month
        num_weeks = getattr(self, 'current_month_weeks', 5)
        if num_weeks == 4:
            available_height = 1.65*inch
        elif num_weeks == 6:
            available_height = 1.1*inch
        else:  # 5 weeks
            available_height = 1.3*inch

        # Adjust row heights based on content - images with overlay take full space
        if len(cell_data) == 3:  # Day + Image placeholder/error + Text
            row_heights = [0.15*inch, (available_height - 0.6*inch), 0.45*inch]  # Day, image placeholder, text
        elif len(cell_data) == 2 and event_image_path:  # Image with overlay + Text
            row_heights = [available_height - 0.45*inch, 0.45*inch]  # Image takes most space, very small text gap
        elif len(cell_data) == 2:  # Day + Text (no image) or Day + Image (no text)
            if event_image_path:
                row_heights = [available_height]  # Image with overlay takes full space
            else:
                row_heights = [0.15*inch, available_height - 0.15*inch]  # Normal day + text layout
        else:  # Just day
            row_heights = [available_height]

        mini_table = CellTable(cell_data, colWidths=[1.4*inch], rowHeights=row_heights)
        mini_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),     # Day number aligned left
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'), # Image and text centered
            ('VALIGN', (0, 0), (0, 0), 'TOP'),     # Day number at top
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'), # Image and text centered
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))

        return mini_table

    def cleanup_temp_files(self):
        """Clean up temporary image files"""
        if hasattr(self, '_temp_files'):
            for temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    print(f"Error cleaning up temp file {temp_file}: {e}")
            self._temp_files = []

    def generate_with_headers(self):
        """Generate calendar with imported header pages"""
        if not hasattr(self.calendar, 'header'):
            raise ValueError("No header document found for this calendar")

        # First generate the basic calendar
        calendar_pdf = self.generate_calendar_only()

        # Then combine with headers
        return self.combine_with_headers(calendar_pdf)

    def combine_with_headers(self, calendar_pdf):
        """Merge calendar pages into the complete header document"""
        header = self.calendar.header

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as combined_file:
            writer = PdfWriter()

            # Read header document (complete 14-page document)
            with open(header.document.path, 'rb') as header_file:
                header_reader = PdfReader(header_file)

                # Read calendar PDF (our 12 month pages)
                calendar_content = io.BytesIO(calendar_pdf.read())
                calendar_reader = PdfReader(calendar_content)

                # Get the starting page for January from the form
                january_page_index = header.january_page - 1  # Convert to 0-based index

                # First, add all pages before the January header
                for page_idx in range(january_page_index):
                    if page_idx < len(header_reader.pages):
                        writer.add_page(header_reader.pages[page_idx])

                # Now interleave header pages with our calendar pages for each month
                for month in range(12):
                    # Add the header page for this month
                    header_page_idx = january_page_index + month
                    if header_page_idx < len(header_reader.pages):
                        writer.add_page(header_reader.pages[header_page_idx])

                    # Add our corresponding calendar page
                    if month < len(calendar_reader.pages):
                        writer.add_page(calendar_reader.pages[month])

                # Add any remaining pages after December (like back cover)
                last_month_header_idx = january_page_index + 12
                for page_idx in range(last_month_header_idx, len(header_reader.pages)):
                    writer.add_page(header_reader.pages[page_idx])

            # Write combined PDF
            with open(combined_file.name, 'wb') as output_file:
                writer.write(output_file)

            # Read the combined file and create Django file object
            with open(combined_file.name, 'rb') as f:
                content = f.read()

            os.unlink(combined_file.name)

            filename = f"calendar_{self.year}_with_headers.pdf"
            return ContentFile(content, name=filename)

    def generate_combined_spread(self):
        """Generate calendar as 2-page spreads (8.5x11 landscape)"""
        if not hasattr(self.calendar, 'header'):
            raise ValueError("No header document found for combined spread generation")

        header = self.calendar.header

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as spread_file:
            doc = SimpleDocTemplate(
                spread_file.name,
                pagesize=landscape(letter),  # 11x8.5 inches
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36
            )

            story = []

            # Read header document
            with open(header.document.path, 'rb') as header_file:
                header_reader = PdfReader(header_file)

                for month in range(1, 13):
                    # Create spread for this month
                    spread_content = self.create_month_spread(month, header_reader, header.january_page)
                    story.extend(spread_content)

            doc.build(story)

            # Create Django file object
            with open(spread_file.name, 'rb') as f:
                content = f.read()

            os.unlink(spread_file.name)

            filename = f"calendar_{self.year}_combined_spread.pdf"
            return ContentFile(content, name=filename)

    def create_month_spread(self, month_num, header_reader, january_page):
        """Create a 2-page spread for a month"""
        content = []

        # Calculate which header page to use
        header_page_index = (january_page - 1 + month_num - 1) % len(header_reader.pages)

        # Add header section (top half of page)
        if header_page_index < len(header_reader.pages):
            # Note: In a real implementation, you'd need to extract and position the header image
            # This is a simplified version
            header_text = Paragraph(f"Header for {cal.month_name[month_num]} {self.year}", self.month_style)
            content.append(header_text)
            content.append(Spacer(1, 100))  # Space for header content

        # Add calendar section (bottom half of page)
        month_calendar = self.generate_month_content(month_num)
        content.extend(month_calendar)

        # Add page break after each month
        from reportlab.platypus import PageBreak
        content.append(PageBreak())

        return content