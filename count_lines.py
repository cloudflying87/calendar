#!/usr/bin/env python3
"""
Generic Line Counter Script
Counts lines of code in various file types within the current directory and subdirectories.
"""

import os
import argparse
from collections import defaultdict
from pathlib import Path

def get_file_extensions():
    """Define file extensions and their categories"""
    return {
        'Python': ['.py'],
        'JavaScript': ['.js', '.jsx', '.ts', '.tsx'],
        'Web': ['.html', '.htm', '.css', '.scss', '.sass', '.less'],
        'Java': ['.java'],
        'C/C++': ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'],
        'C#': ['.cs'],
        'PHP': ['.php'],
        'Ruby': ['.rb'],
        'Go': ['.go'],
        'Rust': ['.rs'],
        'Swift': ['.swift'],
        'Kotlin': ['.kt'],
        'SQL': ['.sql'],
        'Shell': ['.sh', '.bash', '.zsh'],
        'Config': ['.json', '.yaml', '.yml', '.xml', '.toml', '.ini', '.conf'],
        'Markdown': ['.md', '.markdown'],
        'R': ['.r', '.R'],
        'MATLAB': ['.m'],
        'Perl': ['.pl', '.pm'],
        'Scala': ['.scala'],
        'Lua': ['.lua'],
        'Dart': ['.dart'],
        'Vue': ['.vue'],
        'Svelte': ['.svelte']
    }

def should_ignore_path(path, ignore_patterns):
    """Check if a path should be ignored based on patterns"""
    path_str = str(path).lower()
    for pattern in ignore_patterns:
        if pattern in path_str:
            return True
    return False

def count_lines_in_file(file_path):
    """Count lines in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for _ in f)
    except Exception:
        try:
            # Try with different encoding
            with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

def count_lines(directory='.', include_hidden=False, custom_extensions=None):
    """Count lines of code in the specified directory"""
    
    # Default ignore patterns
    ignore_patterns = [
        'node_modules', '.git', '__pycache__', '.pytest_cache',
        'venv', 'env', '.env', 'virtualenv', '.venv',
        'build', 'dist', 'target', 'bin', 'obj',
        '.idea', '.vscode', '.vs', 'coverage',
        'migrations', 'static/admin', 'staticfiles'
    ]
    
    # Get file extensions
    extensions = get_file_extensions()
    
    # Add custom extensions if provided
    if custom_extensions:
        extensions['Custom'] = custom_extensions
    
    # Create extension to category mapping
    ext_to_category = {}
    for category, exts in extensions.items():
        for ext in exts:
            ext_to_category[ext] = category
    
    # Count lines by category
    category_stats = defaultdict(lambda: {'lines': 0, 'files': 0, 'file_list': []})
    total_lines = 0
    total_files = 0
    
    directory_path = Path(directory)
    
    for file_path in directory_path.rglob('*'):
        # Skip directories
        if file_path.is_dir():
            continue
            
        # Skip hidden files unless requested
        if not include_hidden and any(part.startswith('.') for part in file_path.parts):
            continue
            
        # Skip ignored paths
        if should_ignore_path(file_path, ignore_patterns):
            continue
            
        # Check if file extension matches our categories
        file_ext = file_path.suffix.lower()
        if file_ext in ext_to_category:
            category = ext_to_category[file_ext]
            lines = count_lines_in_file(file_path)
            
            category_stats[category]['lines'] += lines
            category_stats[category]['files'] += 1
            category_stats[category]['file_list'].append((str(file_path), lines))
            
            total_lines += lines
            total_files += 1
    
    return category_stats, total_lines, total_files

def format_number(num):
    """Format number with commas"""
    return f"{num:,}"

def print_results(category_stats, total_lines, total_files, show_files=False):
    """Print formatted results"""
    
    print("=" * 60)
    print(f"📊 CODE LINE COUNTER")
    print("=" * 60)
    
    if not category_stats:
        print("No code files found in the current directory.")
        return
    
    # Sort categories by line count (descending)
    sorted_categories = sorted(category_stats.items(), 
                             key=lambda x: x[1]['lines'], 
                             reverse=True)
    
    print(f"{'Category':<15} {'Files':<8} {'Lines':<12} {'Percentage':<10}")
    print("-" * 60)
    
    for category, stats in sorted_categories:
        percentage = (stats['lines'] / total_lines * 100) if total_lines > 0 else 0
        print(f"{category:<15} {stats['files']:<8} {format_number(stats['lines']):<12} {percentage:.1f}%")
        
        if show_files:
            for file_path, lines in sorted(stats['file_list'], key=lambda x: x[1], reverse=True)[:5]:
                rel_path = os.path.relpath(file_path)
                print(f"    📁 {rel_path}: {format_number(lines)} lines")
            if len(stats['file_list']) > 5:
                print(f"    ... and {len(stats['file_list']) - 5} more files")
            print()
    
    print("-" * 60)
    print(f"{'TOTAL':<15} {total_files:<8} {format_number(total_lines):<12} 100.0%")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='Count lines of code in a directory')
    parser.add_argument('directory', nargs='?', default='.', 
                       help='Directory to analyze (default: current directory)')
    parser.add_argument('--include-hidden', action='store_true',
                       help='Include hidden files and directories')
    parser.add_argument('--show-files', action='store_true',
                       help='Show top files for each category')
    parser.add_argument('--extensions', nargs='+',
                       help='Custom file extensions to include (e.g., .custom .special)')
    
    args = parser.parse_args()
    
    # Validate directory
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory")
        return 1
    
    print(f"Analyzing directory: {os.path.abspath(args.directory)}")
    
    # Count lines
    category_stats, total_lines, total_files = count_lines(
        directory=args.directory,
        include_hidden=args.include_hidden,
        custom_extensions=args.extensions
    )
    
    # Print results
    print_results(category_stats, total_lines, total_files, show_files=args.show_files)
    
    return 0

if __name__ == '__main__':
    exit(main())