# Calendar Builder

A comprehensive web application for creating custom photo calendars with professional PDF output. Upload photos, crop them perfectly, organize by dates, and generate beautiful calendar PDFs with optional custom headers.

## 🎯 Features Overview

### **📅 Calendar Management**
- Create calendars for any year (1900-2100)
- Copy events and photos from previous years
- Multi-user support with secure authentication
- Organized calendar overview with event counts

### **📷 Advanced Photo Management**
- **Interactive Photo Editor**: Upload any photo and crop to perfect calendar dimensions (320×200px)
- **Bulk Upload**: Process multiple photos at once using filename format (`MMDD_eventname.jpg`)
- **Smart Resizing**: Automatic optimization for calendar display
- **Format Support**: JPG, JPEG, PNG, GIF (up to 10MB per image)

### **✏️ Event Management**
- Add events to any calendar date
- Edit event names and photos seamlessly
- Holiday management with automatic date calculation
- Visual event editing with photo preview

### **📊 PDF Generation**
- **Calendar Only**: Clean calendar grid with photos and events
- **With Headers**: Merge with custom header documents
- **Combined Spread**: Landscape format for printing
- Professional layout with optimized spacing

### **💾 Data Management**
- **Download All Photos**: Export organized ZIP files by month
- **Copy Calendars**: Duplicate entire calendars to new years
- **Photo Backup**: Maintain photo quality for reuse
- **Event Manifest**: Detailed listing of all calendar events

## 🚀 Quick Start

### Development Setup
```bash
# Clone and setup
git clone <repository>
cd calendar
pyenv virtualenv 3.11+ calendar-builder
pyenv activate calendar-builder
pip install -r requirements/development.txt

# Initialize database
python manage.py migrate
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Production Deployment
```bash
# Full deployment with backup
./build.sh -r -d $(date +%Y%m%d)

# Soft rebuild (preserve data)
./build.sh -s
```

## 📖 User Guide

### **Creating Your First Calendar**

1. **Create Calendar**: Choose year and optionally copy from existing calendar
2. **Add Photos**:
   - **Single Photo**: Use "Upload & Edit Photo" for interactive cropping
   - **Multiple Photos**: Use "Bulk Upload" with proper filename format
3. **Manage Events**: Edit event names, change photos, or remove events
4. **Add Holidays**: Select holidays with optional custom images
5. **Upload Headers**: Add custom header documents for professional look
6. **Generate PDF**: Choose format and download your calendar

### **Photo Workflows**

#### **Interactive Photo Editor** (Recommended)
```
Upload Any Photo → Crop to Perfect Size → Choose Date & Event Name → Save
```
- **Benefits**: See photo while naming, perfect cropping, any filename
- **Best For**: Individual photos, new events, photo editing

#### **Bulk Upload** (Fast Processing)
```
Rename Files (MMDD_eventname.jpg) → Select Multiple → Upload → Auto-Process
```
- **Benefits**: Process many photos quickly
- **Best For**: Pre-organized photos, batch processing

### **File Naming Convention** (Bulk Upload)
```
Format: MMDD_eventname.extension
Examples:
- 0121_Brynn_Birthday.jpg    → January 21: Brynn Birthday
- 0704_Independence_Day.png  → July 4: Independence Day
- 1225 Christmas.gif         → December 25: Christmas
```

### **Advanced Features**

#### **Copy Calendar to New Year**
1. Go to "Create Calendar"
2. Select year and source calendar
3. All events and photos automatically copied
4. Edit as needed for new year

#### **Download All Photos**
1. Go to calendar detail page
2. Click "Download All Photos"
3. Receive organized ZIP file:
   ```
   Calendar-2025-Photos.zip
   ├── 01-January/
   │   ├── 0101_new_years.jpg
   │   └── 0121_birthday.jpg
   ├── 02-February/
   │   └── 0214_valentine.jpg
   └── events_list.txt
   ```

#### **Event Photo Management**
- **Add Photo**: Click "Add Photo" on events without images
- **Change Photo**: Click "Change Photo" → Full editor workflow
- **Remove Photo**: One-click photo removal
- **Seamless Flow**: Returns to event edit after cropping

## 🏗️ Technical Architecture

### **Backend Stack**
- **Framework**: Django 5.0+ with Python 3.11+
- **Database**: PostgreSQL (production) / SQLite (development)
- **Image Processing**: Pillow with optimized resizing
- **PDF Generation**: ReportLab with custom layouts
- **File Storage**: Local filesystem with organized paths

### **Frontend Features**
- **Photo Cropping**: Cropper.js with 1.6:1 aspect ratio lock
- **Responsive Design**: Mobile-first with touch support
- **Interactive Forms**: Smart date validation and file handling
- **Live Previews**: Real-time calendar preview during cropping

### **Key Models**
- **Calendar**: Year-based calendar container
- **CalendarEvent**: Individual events with photos
- **CalendarHeader**: Custom header documents
- **Holiday**: Holiday management with date calculation
- **GeneratedCalendar**: PDF generation tracking

## 📁 Project Structure

```
calendar/
├── apps/
│   └── calendars/          # Main calendar application
│       ├── models.py       # Data models
│       ├── views.py        # Business logic
│       ├── forms.py        # Form handling
│       ├── urls.py         # URL routing
│       └── utils.py        # PDF generation
├── templates/
│   └── calendars/          # HTML templates
├── static/
│   ├── css/               # Styling
│   └── js/                # JavaScript (Cropper.js)
├── media/
│   ├── calendar_images/   # Event photos
│   ├── calendar_headers/  # Header documents
│   └── generated_calendars/ # PDF output
└── config/                # Django configuration
```

## 🔧 Configuration

### **Environment Variables**
```bash
SECRET_KEY=your-secret-key
DEBUG=False
DB_NAME=calendar_db
DB_USER=calendar_user
DB_PASSWORD=secure-password
MEDIA_ROOT=/path/to/media
STATIC_ROOT=/path/to/static
```

### **Image Settings**
- **Target Dimensions**: 320×200 pixels (1.6:1 ratio)
- **PDF Render Size**: 80×50 pixels for calendar cells
- **Max Upload Size**: 10MB per image
- **Supported Formats**: JPG, JPEG, PNG, GIF

### **PDF Generation**
- **Page Size**: Landscape letter (11×8.5 inches)
- **Calendar Grid**: 7 columns × variable rows
- **Image Quality**: 85% JPEG compression
- **Font**: Times (headers), Helvetica (body)

## 🎨 Customization

### **Calendar Styling**
- Modify `apps/calendars/utils.py` for PDF layout
- Update `static/css/` for web interface styling
- Customize colors via CSS variables

### **Photo Processing**
- Adjust target dimensions in `models.py`
- Modify crop ratios in `photo_crop.html`
- Update image quality settings

### **Holiday Management**
- Add holidays in `models.py` HOLIDAY_CHOICES
- Implement date calculation in HolidayCalculator
- Update holiday forms and templates

## 🔒 Security Features

- **User Authentication**: Django built-in with session management
- **File Validation**: Extension and size checking
- **SQL Injection Protection**: Django ORM
- **CSRF Protection**: Token validation on forms
- **User Isolation**: Events scoped to calendar owners

## 📊 Performance Optimizations

- **Image Processing**: Efficient PIL operations with LANCZOS resampling
- **Database Queries**: Optimized with select_related and prefetch_related
- **File Storage**: Organized directory structure
- **PDF Generation**: Chunked processing for large calendars

## 🐛 Troubleshooting

### **Common Issues**

**Photo Upload Fails**
- Check file size (max 10MB)
- Verify supported format (JPG, PNG, GIF)
- Ensure sufficient disk space

**PDF Generation Errors**
- Verify all event images exist
- Check ReportLab installation
- Ensure proper file permissions

**Bulk Upload Not Working**
- Check filename format: `MMDD_eventname.ext`
- Verify date validity (no Feb 30, etc.)
- Ensure unique dates per calendar

### **Development Commands**
```bash
# Check for issues
python manage.py check

# Reset database
python manage.py flush

# Create test data
python manage.py shell
>>> from apps.calendars.models import Calendar
>>> Calendar.objects.create(user_id=1, year=2025)

# Collect static files
python manage.py collectstatic
```

## 📚 Documentation

- **Project Memory**: `CLAUDE.md` - Complete development history
- **Setup Guide**: `docs/SETUP_GUIDE.md` - Detailed installation
- **Style Guide**: `docs/STYLE_GUIDE.md` - Design standards
- **Coding Guide**: `docs/CODING_GUIDE.md` - Development practices

## 🤝 Contributing

1. Follow the coding standards in `docs/CODING_GUIDE.md`
2. Update `CLAUDE.md` with any significant changes
3. Test both photo editor and bulk upload workflows
4. Ensure PDF generation works for all calendar types

## 📝 License

[Add your license information here]

## 🚧 Future Enhancements

- **Photo Combining**: Multi-photo collages for single events
- **Calendar Themes**: Customizable color schemes and layouts
- **Shared Calendars**: Collaborative calendar editing
- **Mobile App**: Native iOS/Android applications
- **Cloud Storage**: Integration with AWS S3 or similar
- **Advanced PDF**: Custom fonts, layouts, and branding

---

**Last Updated**: September 2025
**Version**: 1.0
**Maintained By**: [Your Name/Organization]
