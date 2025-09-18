#!/usr/bin/env python3
"""
Django Project Setup Validation Script

Run this after project setup to verify everything is working correctly.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Optional

class SetupValidator:
    def __init__(self):
        self.project_dir = Path.cwd()
        self.errors = []
        self.warnings = []
        self.passed = []
        
    def run_validation(self) -> bool:
        """Run all validation checks."""
        print("🔍 Validating project setup...")
        print("=" * 50)
        
        # Core file structure
        self.check_project_structure()
        self.check_django_files()
        self.check_docker_files()
        self.check_environment_files()
        
        # Dependencies and tools
        self.check_python_environment()
        self.check_docker_installation()
        
        # Configuration
        self.check_django_settings()
        self.check_database_config()
        
        # Optional features
        self.check_cloudflare_setup()
        self.check_git_setup()
        
        # Show results
        self.show_results()
        
        return len(self.errors) == 0
    
    def check_project_structure(self):
        """Verify the expected directory structure exists."""
        required_dirs = [
            'apps/core',
            'config/settings',
            'static/css',
            'templates',
            'docs',
            'requirements',
        ]
        
        for dir_path in required_dirs:
            if (self.project_dir / dir_path).exists():
                self.passed.append(f"✅ Directory structure: {dir_path}")
            else:
                self.errors.append(f"❌ Missing directory: {dir_path}")
    
    def check_django_files(self):
        """Check for essential Django files."""
        required_files = [
            'manage.py',
            'config/__init__.py',
            'config/settings/__init__.py',
            'config/settings/base.py',
            'config/settings/development.py',
            'config/settings/production.py',
            'config/urls.py',
            'config/wsgi.py',
        ]
        
        for file_path in required_files:
            if (self.project_dir / file_path).exists():
                self.passed.append(f"✅ Django file: {file_path}")
            else:
                self.errors.append(f"❌ Missing Django file: {file_path}")
    
    def check_docker_files(self):
        """Check Docker configuration files."""
        docker_files = [
            ('docker-compose.yml', True),
            ('Dockerfile', True),
            ('docker-entrypoint.sh', True),
            ('nginx/Dockerfile', False),
            ('nginx/nginx.conf', False),
        ]
        
        for file_path, required in docker_files:
            if (self.project_dir / file_path).exists():
                self.passed.append(f"✅ Docker file: {file_path}")
            elif required:
                self.errors.append(f"❌ Missing Docker file: {file_path}")
            else:
                self.warnings.append(f"⚠️  Optional Docker file missing: {file_path}")
    
    def check_environment_files(self):
        """Check environment configuration files."""
        if (self.project_dir / '.env.example').exists():
            self.passed.append("✅ Environment template: .env.example")
        else:
            self.errors.append("❌ Missing .env.example file")
        
        if (self.project_dir / '.env').exists():
            self.warnings.append("⚠️  .env file exists (good for development)")
        else:
            self.warnings.append("⚠️  No .env file (you'll need to create one)")
        
        if (self.project_dir / '.gitignore').exists():
            self.passed.append("✅ Git ignore file exists")
        else:
            self.errors.append("❌ Missing .gitignore file")
    
    def check_python_environment(self):
        """Check Python and virtual environment setup."""
        try:
            python_version = subprocess.check_output([
                sys.executable, '--version'
            ], text=True).strip()
            self.passed.append(f"✅ Python: {python_version}")
        except subprocess.CalledProcessError:
            self.errors.append("❌ Python version check failed")
        
        # Check if we're in a virtual environment
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            self.passed.append("✅ Virtual environment: Active")
        else:
            self.warnings.append("⚠️  No virtual environment detected")
    
    def check_docker_installation(self):
        """Check if Docker is installed and accessible."""
        try:
            docker_version = subprocess.check_output([
                'docker', '--version'
            ], text=True, stderr=subprocess.DEVNULL).strip()
            self.passed.append(f"✅ {docker_version}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.warnings.append("⚠️  Docker not found (install for production deployment)")
        
        try:
            compose_version = subprocess.check_output([
                'docker', 'compose', 'version'
            ], text=True, stderr=subprocess.DEVNULL).strip()
            self.passed.append(f"✅ Docker Compose available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.warnings.append("⚠️  Docker Compose not found")
    
    def check_django_settings(self):
        """Validate Django settings files."""
        settings_base = self.project_dir / 'config/settings/base.py'
        if settings_base.exists():
            content = settings_base.read_text()
            if 'apps.core' in content:
                self.passed.append("✅ Django settings: Core app configured")
            else:
                self.warnings.append("⚠️  Core app not in INSTALLED_APPS")
        
        # Check if SECRET_KEY is properly configured
        env_example = self.project_dir / '.env.example'
        if env_example.exists():
            content = env_example.read_text()
            if 'SECRET_KEY' in content:
                self.passed.append("✅ SECRET_KEY template configured")
            else:
                self.errors.append("❌ SECRET_KEY not in .env.example")
    
    def check_database_config(self):
        """Check database configuration."""
        env_example = self.project_dir / '.env.example'
        if env_example.exists():
            content = env_example.read_text()
            if 'DB_NAME' in content and 'DB_USER' in content:
                self.passed.append("✅ Database configuration template")
            else:
                self.errors.append("❌ Database configuration incomplete")
    
    def check_cloudflare_setup(self):
        """Check Cloudflare tunnel configuration if present."""
        cloudflared_dir = self.project_dir / 'cloudflared'
        if cloudflared_dir.exists():
            if (cloudflared_dir / 'config.yml').exists():
                self.passed.append("✅ Cloudflare: Configuration template")
            else:
                self.warnings.append("⚠️  Cloudflare directory exists but config.yml missing")
            
            if (cloudflared_dir / 'README.md').exists():
                self.passed.append("✅ Cloudflare: Setup instructions")
    
    def check_git_setup(self):
        """Check Git repository initialization."""
        if (self.project_dir / '.git').exists():
            self.passed.append("✅ Git repository initialized")
            
            try:
                # Check if there are any commits
                subprocess.check_output([
                    'git', 'rev-parse', 'HEAD'
                ], stderr=subprocess.DEVNULL)
                self.passed.append("✅ Git: Has commits")
            except subprocess.CalledProcessError:
                self.warnings.append("⚠️  Git initialized but no commits yet")
        else:
            self.warnings.append("⚠️  Git repository not initialized")
    
    def show_results(self):
        """Display validation results."""
        print("\n" + "=" * 50)
        print("📊 Validation Results")
        print("=" * 50)
        
        if self.passed:
            print(f"\n✅ PASSED ({len(self.passed)} checks)")
            for item in self.passed:
                print(f"  {item}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)} items)")
            for item in self.warnings:
                print(f"  {item}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)} items)")
            for item in self.errors:
                print(f"  {item}")
        
        print("\n" + "=" * 50)
        
        if self.errors:
            print("❌ Setup validation FAILED")
            print("Please fix the errors above before proceeding.")
            return False
        elif self.warnings:
            print("⚠️  Setup validation passed with warnings")
            print("Consider addressing the warnings for optimal setup.")
        else:
            print("✅ Setup validation PASSED")
            print("Your project is ready for development!")
        
        print("\n🚀 Next steps:")
        if not self.errors:
            print("  1. Create .env file from .env.example")
            print("  2. Run: python manage.py migrate")
            print("  3. Run: python manage.py runserver")
            print("  4. Visit: http://localhost:8000")
        
        return True

def main():
    """Main validation function."""
    validator = SetupValidator()
    success = validator.run_validation()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()