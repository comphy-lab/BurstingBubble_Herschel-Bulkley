import os
import subprocess
import re
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any, Union
import html
import json

# Parse command line arguments
parser = argparse.ArgumentParser(description='Generate documentation from source files.')
parser.add_argument('--debug', action='store_true', help='Enable debug output')
parser.add_argument('--force-rebuild', action='store_true', help='Force rebuilding of all HTML files, including existing ones')
args = parser.parse_args()

# Global debug flag
DEBUG = args.debug
FORCE_REBUILD = args.force_rebuild

def debug_print(message):
    """Print debug messages only if debug mode is enabled."""
    if DEBUG:
        print(message)

def calculate_asset_prefix(output_html_path: Path, docs_dir: Path) -> str:
    """
    Calculate the relative path prefix for assets based on HTML file depth.

    Args:
        output_html_path: Path of the generated HTML file.
        docs_dir: The root directory for documentation.

    Returns:
        A string representing the relative prefix (e.g., '.', '..', '../..').
    """
    try:
        # Special case for the main index.html at docs root
        if output_html_path.name == "index.html" and output_html_path.parent == docs_dir:
            return "."  # Use current directory for index.html
        
        # For all other files, calculate their depth from docs_dir
        depth = len(output_html_path.relative_to(docs_dir).parents) - 1
        if depth <= 0:
            return "."  # Root level
        else:
            return "/".join([".."] * depth)
    except ValueError:
        # Handle cases where output_html_path is not within docs_dir (should not happen)
        return "."

def extract_seo_metadata(file_path: Path, file_content: str) -> Dict[str, str]:
    """
    Extract SEO metadata from the given file content.
    
    This function scans the file content to obtain SEO metadata by extracting a meta description and a set of keywords. The description is derived from the first comment block in the file, cleaned of markdown formatting, and truncated to approximately 160 characters. Keywords are identified by matching predefined technical patterns in the content and by extracting meaningful tokens from the file name. The metadata is returned as a dictionary with keys "description" and "keywords".
    """
    metadata = {}
    
    # Extract first paragraph as description (up to 160 chars)
    # Try to find a documentation comment or a paragraph with actual text, not code
    description_match = re.search(r'^\s*#\s*(.*?)\s*$\s*([a-zA-Z].*?)(?=^\s*#|\Z)', file_content, re.MULTILINE | re.DOTALL)
    if description_match:
        # First try the paragraph after the heading
        description = description_match.group(2).strip()
        
        # If that's empty or just code, use the heading itself
        if not description or description.startswith(('```', '`', '#', '//')):
            description = description_match.group(1).strip()
        
        # If that's empty or just code, use the heading itself
        if not description or description.startswith(('```', '`', '#', '//')):
            description = description_match.group(1).strip()

# Configuration
# Assume the script is in .github/scripts, REPO_ROOT is the parent of .github
REPO_ROOT = Path(__file__).parent.parent.parent
SOURCE_DIRS = ['src-local', 'simulationCases', 'postProcess']  # Directories within REPO_ROOT to scan
DOCS_DIR = REPO_ROOT / 'docs'
README_PATH = REPO_ROOT / 'README.md'
INDEX_PATH = DOCS_DIR / 'index.html'
# --- New configuration based on page2html ---
BASILISK_DIR = REPO_ROOT / 'basilisk'  # Assuming basilisk dir is at the root
DARCSIT_DIR = BASILISK_DIR / 'src' / 'darcsit'
TEMPLATE_PATH = REPO_ROOT / '.github' / 'assets' / 'custom_template.html'  # Use the modified local template
LITERATE_C_SCRIPT = DARCSIT_DIR / 'literate-c'  # Path to the literate-c script
BASE_URL = "/"  # Relative base URL for links within the site
CSS_PATH = REPO_ROOT / '.github' / 'assets' / 'css' / 'custom_styles.css'  # Path to custom CSS

# Get repository name from directory
REPO_NAME = REPO_ROOT.name

# Read domain from CNAME file or use default
try:
    CNAME_PATH = REPO_ROOT / 'CNAME'
    BASE_DOMAIN = f"https://{CNAME_PATH.read_text().strip()}" if CNAME_PATH.exists() else "https://test.comphy-lab.org"
except Exception as e:
    print(f"Warning: Could not read CNAME file: {e}")
    BASE_DOMAIN = "https://test.comphy-lab.org"

def extract_h1_from_readme(readme_path: Path) -> str:
    """
    Extract the first markdown H1 header from a README file.
    
    This function reads the file at the specified path using UTF-8 encoding and searches for the
    first line that starts with "# ". If an H1 header is found, the function returns its trimmed text.
    If no header is present or an error occurs during reading, it returns the default title "Documentation".
    """
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Look for # Heading pattern
            h1_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            if h1_match:
                return h1_match.group(1).strip()
            else:
                debug_print("Warning: No h1 heading found in README.md")
                return "Documentation"
    except Exception as e:
        print(f"Error reading README.md: {e}")
        return "Documentation"


# Dynamically get the wiki title from README.md
WIKI_TITLE = extract_h1_from_readme(README_PATH)


def process_template_for_assets(template_path: Path) -> str:
    """
    Process the custom template to ensure correct asset paths.
    
    This function reads the template HTML file and ensures that all asset references
    use the correct paths relative to the root. It converts paths like $base$/assets/...
    to the correct format for the generated documentation.
    
    Args:
        template_path: Path to the custom HTML template
        
    Returns:
        The processed template content as a string
    """
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
            
        # Print repository name for debugging
        print(f"Repository name: {REPO_NAME}")
        
        debug_print("Template processed for correct asset paths")
        return template_content
    except Exception as e:
        print(f"Error processing template for assets: {e}")
        return ""


def validate_config() -> bool:
    """
    Validates that all required configuration paths exist.
    
    Checks if the necessary directories (BASILISK_DIR and DARCSIT_DIR) and files (TEMPLATE_PATH and the literate-c script)
    are present. If any path is missing, an error is printed and the function returns False; otherwise, it returns True.
    """
    global TEMPLATE_PATH
    
    essential_paths = [
        (BASILISK_DIR, "BASILISK_DIR"),
        (DARCSIT_DIR, "DARCSIT_DIR"),
        (TEMPLATE_PATH, "TEMPLATE_PATH"),
        (LITERATE_C_SCRIPT, "literate-c script")
    ]

    for path, name in essential_paths:
        if not (path.is_dir() if name.endswith("DIR") else path.is_file()):
            print(f"Error: {name} not found at {path}")
            return False
    
    # Process the template to ensure correct asset paths
    # Process the template to ensure correct asset paths
    processed_template = process_template_for_assets(TEMPLATE_PATH)
    if not processed_template:
        return False
    # Create a temporary template file with processed content
    temp_template_path = TEMPLATE_PATH.with_suffix('.temp.html')
    
    # Clean up any existing temporary file
    if temp_template_path.exists():
        try:
            temp_template_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete existing temporary template: {e}")
    
    try:
        with open(temp_template_path, 'w', encoding='utf-8') as f:
            f.write(processed_template)
        # Replace the template path with the temporary one
        TEMPLATE_PATH = temp_template_path
    except Exception as e:
        print(f"Error creating temporary template file: {e}")
        return False
    
    return True


def find_source_files(root_dir: Path, source_dirs: List[str]) -> List[Path]:
    """
    Efficiently finds source files of supported types in specified directories.
    Skips .dat files. Treats Makefile as a source file.
    """
    valid_exts = {'.c', '.h', '.py', '.sh', '.ipynb'}
    valid_names = {'Makefile'}
    files = set()

    for dir_name in source_dirs:
        src_path = root_dir / dir_name
        if src_path.is_dir():
            for f in src_path.rglob('*'):
                if f.is_file():
                    if f.name in valid_names:
                        files.add(f)
                    elif f.suffix in valid_exts and not f.name.endswith('.dat'):
                        files.add(f)

    # Also search for .sh files and Makefiles directly in the root directory
    for f in root_dir.iterdir():
        if f.is_file():
            if f.name in valid_names:
                files.add(f)
            elif f.suffix in valid_exts and not f.name.endswith('.dat'):
                files.add(f)

    return sorted(files)


def process_markdown_file(file_path: Path) -> str:
    """
    Process markdown file content for HTML conversion.
    
    Args:
        file_path: Path to the markdown file
        
    Returns:
        Content ready for pandoc conversion
    
    Raises:
        Exception: If file reading fails
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    return file_content


def process_shell_file(file_path: Path) -> str:
    """
    Reads a shell script file and returns its content as a Markdown-formatted bash code block.
    
    Args:
        file_path: Path to the shell script file.
    
    Returns:
        The shell script content wrapped in a Markdown fenced code block labeled 'bash'.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    return f"```bash\n{file_content}\n```"


def process_jupyter_notebook(file_path: Path) -> str:
    """
    Generates an HTML snippet to embed a Jupyter notebook with preview and external links.
    
    Reads a Jupyter notebook file, extracts its title, description, and key features from the first markdown cell if available, and produces HTML that embeds a live preview via nbviewer.org. The output includes buttons to download the notebook, view it on nbviewer, or open it in Google Colab, along with error handling for preview failures.
    
    Args:
        file_path: Path to the Jupyter notebook (.ipynb) file.
    
    Returns:
        An HTML string for embedding the notebook preview and providing external access options.
    """
    notebook_filename = file_path.name
    
    try:
        # Read the notebook to extract basic information
        with open(file_path, 'r', encoding='utf-8') as f:
            notebook_content = f.read()
        
        # Get the notebook's directory within the repository
        rel_path = file_path.relative_to(REPO_ROOT).parent
        if rel_path.as_posix() == '.':
            notebook_path = notebook_filename
        else:
            notebook_path = f"{rel_path}/{notebook_filename}"
            
        # Extract title and description if available
        notebook_title = notebook_filename
        notebook_description = ""
        notebook_features = []
        
        try:
            notebook_data = json.loads(notebook_content)
            # Try to get a better title from the notebook
            for cell in notebook_data.get('cells', []):
                if cell.get('cell_type') == 'markdown':
                    source = ''.join(cell.get('source', []))
                    # Look for a title in the first cell
                    title_match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
                    if title_match:
                        notebook_title = title_match.group(1).strip()
                        # Look for description text after the title
                        desc_match = re.search(r'^#\s+.+\n\n(.+?)(?=\n\n|\Z)', source, re.DOTALL | re.MULTILINE)
                        if desc_match:
                            notebook_description = desc_match.group(1).strip()
                            # Look for bullet points that might be features
                            features_match = re.findall(r'^\s*[\*\-\+]\s+(.+)$', source, re.MULTILINE)
                            if features_match:
                                notebook_features = [f.strip() for f in features_match[:3]]  # Limit to 3 features
                        break
        except (json.JSONDecodeError, UnicodeDecodeError):
            # If parsing fails, use defaults
            pass
            
        # Set default description if none found
        if not notebook_description:
            notebook_description = f"This notebook provides visualization and analysis related to {notebook_filename.split('.')[0].replace('-', ' ').replace('_', ' ')}."
            
        # Set default features if none found
        if not notebook_features:
            notebook_features = [
                "Visualization of data and results",
                "Analysis of simulation outputs",
                "Interactive exploration of parameters"
            ]
        
        # Escape user-supplied metadata to prevent XSS
        safe_notebook_title = html.escape(notebook_title)
        safe_notebook_description = html.escape(notebook_description)
        safe_notebook_features = [html.escape(f) for f in notebook_features]
        
        # Create feature list HTML
        features_html = "\n".join([f'<li>{feature}</li>' for feature in safe_notebook_features])
        
        # Create raw HTML output that won't get escaped by pandoc
        # This is key - we use triple backticks with {=html} to tell pandoc to interpret this as raw HTML
        embed_html = f"""# {safe_notebook_title}

```{{=html}}
<div class="jupyter-notebook-embed">
    <h2>Jupyter Notebook: {safe_notebook_title}</h2>
    
    <div class="notebook-action-buttons">
        <a href="{notebook_filename}" download class="notebook-btn download-btn">
            <i class="fa-solid fa-download"></i> Download Notebook
        </a>
        <a href="https://nbviewer.org/github/comphy-lab/{REPO_NAME}/blob/main/{notebook_path}" 
           target="_blank" class="notebook-btn view-btn">
            <i class="fa-solid fa-eye"></i> View in nbviewer
        </a>
        <a href="https://colab.research.google.com/github/comphy-lab/{REPO_NAME}/blob/main/{notebook_path}" 
           target="_blank" class="notebook-btn colab-btn">
            <i class="fa-solid fa-play"></i> Open in Colab
        </a>
    </div>
    
    <div class="notebook-preview">
        <h3>About this notebook</h3>
        <p>{safe_notebook_description}</p>
        
        <h3>Key Features:</h3>
        <ul>
            {features_html}
        </ul>
    </div>
    
    <div class="notebook-tip">
        <p><strong>Tip:</strong> For the best interactive experience, download the notebook or open it in Google Colab.</p>
    </div>

    <!-- Embedded Jupyter Notebook -->
    <div class="embedded-notebook">
        <h3>Notebook Preview</h3>
        <div id="notebook-container-{notebook_filename.replace('.', '-')}" >
            <iframe id="notebook-iframe-{notebook_filename.replace('.', '-')}" 
                    src="https://nbviewer.org/github/comphy-lab/{REPO_NAME}/blob/main/{notebook_path}" 
                    width="100%" height="800px" frameborder="0"
                    onload="checkIframeLoaded('{notebook_filename.replace('.', '-')}')"
                    onerror="handleIframeError('{notebook_filename.replace('.', '-')}')"></iframe>
            <div id="notebook-error-{notebook_filename.replace('.', '-')}" 
                 class="notebook-error-message" style="display: none;">
                <div class="error-container">
                    <i class="fa-solid fa-exclamation-triangle"></i>
                    <h4>Notebook Preview Unavailable</h4>
                    <p>The notebook preview could not be loaded. This may be because:</p>
                    <ul>
                        <li>The notebook file is not yet available in the repository</li>
                        <li>The nbviewer service is temporarily unavailable</li>
                        <li>The repository is private or has access restrictions</li>
                    </ul>
                    <p>You can still download the notebook using the button above or view it directly through one of the external services.</p>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
    .notebook-error-message {{
        padding: 20px;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        margin: 20px 0;
        text-align: center;
    }}
    
    .error-container {{
        max-width: 600px;
        margin: 0 auto;
    }}
    
    .notebook-error-message i {{
        font-size: 2em;
        color: #dc3545;
        margin-bottom: 10px;
    }}
    
    .notebook-error-message h4 {{
        color: #dc3545;
        margin-bottom: 15px;
    }}
    
    .notebook-error-message ul {{
        text-align: left;
        display: inline-block;
        margin: 10px 0;
    }}
</style>

<script>
    function checkIframeLoaded(id) {{
        try {{
            const iframe = document.getElementById('notebook-iframe-' + id);
            // Check if we can access the iframe content
            const iframeContent = iframe.contentWindow || iframe.contentDocument;
            
            // Try to check if iframe contains a 404 or error message
            // This may fail due to cross-origin policies, which is itself a sign the iframe is not working properly
            try {{
                if (iframeContent.document.title.includes('404') || 
                    iframeContent.document.body.textContent.includes('404 Not Found')) {{
                    handleIframeError(id);
                }}
            }} catch (e) {{
                // Cross-origin error might occur, but that's expected for successful loading too
                // So we don't trigger the error handling here
            }}
        }} catch (e) {{
            handleIframeError(id);
        }}
    }}
    
    function handleIframeError(id) {{
        const iframe = document.getElementById('notebook-iframe-' + id);
        const errorDiv = document.getElementById('notebook-error-' + id);
        
        if (iframe && errorDiv) {{
            iframe.style.display = 'none';
            errorDiv.style.display = 'block';
        }}
    }}
    
    // Additional check - try to detect 404 page after the iframe has fully loaded
    document.addEventListener('DOMContentLoaded', function() {{
        const iframes = document.querySelectorAll('iframe[id^="notebook-iframe-"]');
        iframes.forEach(iframe => {{
            iframe.addEventListener('load', function() {{
                const id = iframe.id.replace('notebook-iframe-', '');
                setTimeout(() => checkIframeLoaded(id), 1000); // Check after a slight delay
            }});
        }});
    }});
</script>
```
"""
        return embed_html
    except Exception as e:
        return f"# {notebook_filename}\n\nError processing notebook: {str(e)}"


def process_python_file(file_path: Path) -> str:
    """
    Converts a Python source file into Markdown by separating docstrings and code.
    
    Reads the file, extracts triple-quoted docstrings as plain text, and formats code blocks with Markdown Python fences. The result is a Markdown string suitable for HTML conversion.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    lines = file_content.split('\n')
    processed_lines = []
    in_code_block = False
    code_block = []
    in_docstring = False
    docstring_lines = []
    
    for line in lines:
        # Check for docstring comments (triple quotes)
        if line.strip().startswith('"""') or line.strip().startswith("'''"):
            # If we're in a docstring, end it
            if in_docstring:
                in_docstring = False
                # Add the docstring as text, but skip any lines that only contain quotes
                clean_docstring = []
                for doc_line in docstring_lines:
                    # Skip lines that only contain quotes
                    if doc_line.strip() in ('"""', "'''"):
                        continue
                    # Remove starting/ending quotes from lines that have content
                    doc_line = doc_line.strip()
                    if doc_line.startswith('"""') or doc_line.startswith("'''"):
                        doc_line = doc_line[3:]
                    if doc_line.endswith('"""') or doc_line.endswith("'''"):
                        doc_line = doc_line[:-3]
                    clean_docstring.append(doc_line.strip())
                
                # Only add non-empty lines
                if clean_docstring:
                    processed_lines.append("")
                    processed_lines.extend(clean_docstring)
                    processed_lines.append("")
                docstring_lines = []
            else:
                # Start a new docstring
                in_docstring = True
                # If we're in a code block, end it
                if in_code_block:
                    processed_lines.append("```python")
                    processed_lines.extend(code_block)
                    processed_lines.append("```")
                    code_block = []
                    in_code_block = False
            continue
        
        # If we're in a docstring, add the line to docstring_lines
        if in_docstring:
            docstring_lines.append(line)
            continue
        
        # For regular code lines (including # comments)
        if not in_code_block and line.strip():
            in_code_block = True
            code_block.append(line)
        elif in_code_block:
            code_block.append(line)
        else:
            # Empty line outside of a code block
            processed_lines.append(line)
    
    # End any remaining code block
    if in_code_block:
        processed_lines.append("```python")
        processed_lines.extend(code_block)
        processed_lines.append("```")
    
    # End any remaining docstring
    if in_docstring:
        processed_lines.append("")
        processed_lines.extend(docstring_lines)
        processed_lines.append("")
    
    # Join the processed lines
    return '\n'.join(processed_lines)


def process_c_file(file_path: Path, literate_c_script: Path) -> str:
    """
    Process a C/C++ source file for HTML conversion using literate-C preprocessing.
    
    This function reads the content of a C/C++ file and creates a simple markdown
    representation. It then attempts to run a provided literate-C script on the file to
    generate a preprocessed output suitable for Pandoc conversion. If the literate-C
    processing produces non-empty output, specific markers are replaced with standard
    Pandoc code block markers. If the processing fails or returns empty output, a debug
    message is logged and the fallback markdown version is returned.
    
    Args:
        file_path (Path): Path to the C/C++ source file.
        literate_c_script (Path): Path to the literate-C preprocessing script.
    
    Returns:
        str: Markdown-formatted content ready for Pandoc conversion.
    """
    # First, read the file content directly
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    # Create a markdown representation of the C file
    markdown_content = f"""# {file_path.name}

```c
{file_content}
```
"""
    
    # Run literate-c for additional processing if available
    literate_c_cmd = [str(literate_c_script), str(file_path), '0']  # Use magic=0 for standard C files
    
    try:
        # Run literate-c, capture its output
        preproc_proc = subprocess.Popen(
            literate_c_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            encoding='utf-8'
        )
        content, stderr = preproc_proc.communicate()

        if preproc_proc.returncode == 0 and content.strip():
            # Replace the specific marker literate-c uses with standard pandoc 'c'
            content = content.replace('~~~literatec', '~~~c')
            return content
        else:
            # If literate-c fails or produces no output, use our simple markdown version
            debug_print(f"  [Debug] Using simple markdown for {file_path} due to literate-c error: {stderr}")
            return markdown_content
            
    except Exception as e:
        # If there's any error running literate-c, fall back to simple markdown
        debug_print(f"  [Debug] Using simple markdown for {file_path} due to error: {e}")
        return markdown_content


def prepare_pandoc_input(file_path: Path, literate_c_script: Path) -> str:
    """
    Prepares source file content for Pandoc conversion based on file type.
    
    Selects the appropriate processing function for Markdown, Python, shell, Jupyter notebook, or C/C++ files, returning the content as a string suitable for Pandoc conversion.
    Treats Makefile as a shell script.
    """
    file_suffix = file_path.suffix.lower()
    file_name = file_path.name
    
    if file_suffix == '.md':
        return process_markdown_file(file_path)
    elif file_suffix == '.py':
        return process_python_file(file_path)
    elif file_suffix == '.sh':
        return process_shell_file(file_path)
    elif file_suffix == '.ipynb':
        return process_jupyter_notebook(file_path)
    elif file_name == 'Makefile':
        return process_shell_file(file_path)
    else:  # C/C++ files
        return process_c_file(file_path, literate_c_script)


def run_pandoc(pandoc_input: str, output_html_path: Path, template_path: Path, 
               base_url: str, wiki_title: str, page_url: str, page_title: str,
               asset_path_prefix: str, # Added asset prefix
               seo_metadata: Dict[str, str] = None) -> str:
    """Converts Markdown content to a standalone HTML document using Pandoc.
    
    This function runs Pandoc to transform the provided Markdown input into HTML using a specified
    template and SEO metadata. It assigns HTML variables for the base URL, wiki title, page URL, and
    page title, and saves Pandoc's output to the designated file. After conversion, the function checks
    that the generated HTML contains the proper DOCTYPE and <html> tag, and wraps the content with a
    complete HTML scaffold if necessary. Returns Pandoc's standard output on success or an empty string
    when an error occurs.
      
    Args:
        pandoc_input: The Markdown content to convert.
        output_html_path: File path where the generated HTML is saved.
        template_path: Path to the HTML template file used by Pandoc.
        base_url: Base URL for constructing absolute links.
        wiki_title: Title of the documentation or wiki.
        page_url: URL of the current page.
        page_title: Title of the current page.
        asset_path_prefix: Relative path prefix for assets (e.g., '.', '..')
        seo_metadata: Optional dictionary with SEO metadata (e.g., description, keywords, image).
    
    Returns:
        The standard output from Pandoc if conversion succeeds; otherwise, an empty string.
    """
    if seo_metadata is None:
        seo_metadata = {}
    
    pandoc_cmd = [
        'pandoc',
        '-f', 'markdown+smart+raw_html',  # Use markdown input with smart typography extension and raw HTML
        '-t', 'html5',
        '--standalone',     # Create full HTML doc
        '--template', str(template_path),
        '-V', f'base={base_url}',
        '-V', f'wikititle={wiki_title}',
        '-V', f'pageUrl={page_url}',
        '-V', f'pagetitle={page_title}',
        '-V', f'reponame={REPO_NAME}',
        # Add SEO metadata variables
        '-V', f'description={seo_metadata.get("description", "")}',
        '-V', f'keywords={seo_metadata.get("keywords", "")}',
        '-V', f'image={seo_metadata.get("image", "")}',
        '-V', f'asset_path_prefix={asset_path_prefix}', # Pass prefix to template
        '-o', str(output_html_path)
    ]
    
    # Print pandoc command and input for debugging
    debug_print(f"  [Debug Pandoc] Command: {' '.join(pandoc_cmd)}")
    debug_print(f"  [Debug Pandoc] Input content length: {len(pandoc_input)} chars")
    debug_print(f"  [Debug Pandoc] First 200 chars of input: {pandoc_input[:200]}")
    
    # Run pandoc with input content
    process = subprocess.run(pandoc_cmd, input=pandoc_input, text=True, capture_output=True)
    
    # Print pandoc output for debugging
    debug_print(f"  [Debug Pandoc] Return Code: {process.returncode}")
    if process.stdout:
        debug_print(f"  [Debug Pandoc] STDOUT:\n{process.stdout}")
    if process.stderr:
        debug_print(f"  [Debug Pandoc] STDERR:\n{process.stderr}")
    
    if process.returncode != 0:
        print(f"Error running pandoc: {process.stderr}")
        return ""
    
    # Read the generated HTML and clean up any empty anchor tags
    try:
        with open(output_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Remove empty anchor tags
        content = re.sub(r'<a[^>]*>\s*</a>', '', content)
            
        # Check if the file has proper HTML structure
        if '<!DOCTYPE' not in content or '<html' not in content:
            print(f"Warning: Generated HTML for {output_html_path} is missing DOCTYPE or html tag")
            # Try to fix by adding proper HTML structure
            fixed_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>{wiki_title} - {page_title}</title>
    <meta name="description" content="{seo_metadata.get('description', '')}" />
    <meta name="keywords" content="{seo_metadata.get('keywords', '')}" />
</head>
<body>
{content}
</body>
</html>"""
            content = fixed_content
            
        # Write back the cleaned content
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    except Exception as e:
        print(f"Error verifying HTML structure: {e}")
    
    return process.stdout


def post_process_python_shell_html(html_content: str) -> str:
    """
    Post-processes HTML from Python or shell files for enhanced code block display and navigation.
    
    Wraps code blocks in container divs for styling and copy button support, updates local documentation links to include the `.html` extension, removes dynamic asset path JavaScript, and inserts a script setting `window.repoName` after the opening `<body>` tag.
    
    Args:
        html_content: Raw HTML content generated from a Python or shell file.
    
    Returns:
        The processed HTML content with improved code block containers, corrected documentation links, and repository metadata.
    """
    # Fix any <pre><code> blocks by wrapping them in a container div
    def wrap_pre_code_with_container(match):
        """
        Wraps a matched code block in a container div.
        
        Extracts the full text from a regex match object and encloses it in a <div> element
        with the "code-block-container" class, enabling additional HTML styling.
        
        Args:
            match: A regex match object containing the code block text.
        
        Returns:
            A string with the matched content wrapped in a container div.
        """
        pre_content = match.group(0)
        return f'<div class="code-block-container">{pre_content}</div>'
    
    # Wrap <pre><code> blocks with a container div
    processed_html = re.sub(
        r'<pre[^>]*><code[^>]*>.*?</code></pre>', 
        wrap_pre_code_with_container, 
        html_content, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Also handle code blocks created by pandoc (with sourceCode class)
    def wrap_source_code_with_container(match):
        """
        Wraps matched source code in an HTML container.
        
        Extracts the content from the first capturing group of the regex match object
        and returns it enclosed within a <div> tag having the "code-block-container" class.
        
        Args:
            match: A regex match object with the source code in its first capturing group.
        
        Returns:
            A string with the source code wrapped in a <div class="code-block-container"> tag.
        """
        div_contents = match.group(1)
        return f'<div class="code-block-container">{div_contents}</div>'
    
    processed_html = re.sub(
        r'<div class="sourceCode" id="cb\d+"[^>]*>(.*?)</div>', 
        wrap_source_code_with_container, 
        processed_html, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Fix links to documentation files by appending .html
    def fix_doc_links(match):
        """
        Fixes links to documentation files by appending .html to the href.
        
        This function identifies links that point to other documentation files
        and appends .html to the href attribute if it doesn't already have it.
        
        Args:
            match: A regex match object containing the link tag.
        
        Returns:
            A string with the fixed link.
        """
        link_tag = match.group(0)
        href_match = re.search(r'href="([^"]+)"', link_tag)
        
        if href_match:
            href = href_match.group(1)
            # Skip external links, anchors, and links that already have .html
            if (href.startswith('http') or href.startswith('https') or 
                href.startswith('#') or href.endswith('.html')):
                return link_tag
                
            # Check if the link points to a file in the repository
            if re.search(r'\.(c|h|py|sh|md)$', href):
                # Replace the href with the one that includes .html
                return re.sub(r'href="([^"]+)"', f'href="{href}.html"', link_tag)
        
        return link_tag
    
    # Apply the link fix
    processed_html = re.sub(
        r'<a[^>]+href="[^"]+">[^<]+</a>',
        fix_doc_links,
        processed_html
    )
    
    # Remove all JavaScript related to dynamic base path resolution and asset paths
    # This includes both inline scripts and any JS variables or functions related to paths
    processed_html = re.sub(r'<script[^>]*>\s*// Dynamic base path resolution.*?</script>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<script[^>]*>\s*// Helper function to create dynamic asset paths.*?</script>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<script[^>]*>\s*window\.basePath\s*=.*?</script>', '', processed_html, flags=re.DOTALL)
    processed_html = re.sub(r'<script[^>]*>\s*function\s+assetPath.*?</script>', '', processed_html, flags=re.DOTALL)

    # Add repoName variable to the HTML
    repo_script = f'\n<script>window.repoName = "{REPO_NAME}";</script>\n'
    # Insert after opening body tag
    processed_html = re.sub(r'<body[^>]*>', lambda m: m.group(0) + repo_script, processed_html)

    return processed_html


def run_awk_post_processing(html_content: str, file_path: Path, 
                            repo_root: Path, darcsit_dir: Path) -> str:
    """
    Apply awk post-processing to HTML content from C files.
    
    This function runs the 'decl_anchors.awk' script from the darcsit directory on the
    given HTML content. It determines a tags file path relative to the repository root
    based on the source file, executes the awk script using a temporary file for output,
    and returns the processed HTML. The temporary file is removed after processing.
    
    Args:
        html_content: HTML content to process.
        file_path: Path of the original C source file.
        repo_root: Root directory of the repository for relative path computation.
        darcsit_dir: Directory containing the 'decl_anchors.awk' script.
    
    Returns:
        Processed HTML content.
    
    Raises:
        FileNotFoundError: If the 'decl_anchors.awk' script is not found.
        RuntimeError: If the awk processing fails.
    """
    decl_anchors_script = darcsit_dir / 'decl_anchors.awk'
    if not decl_anchors_script.is_file():
        raise FileNotFoundError(f"decl_anchors.awk script not found at {decl_anchors_script}")
    
    # Construct the expected tags file path relative to the repo root for awk
    relative_tags_path = file_path.relative_to(repo_root).with_suffix(file_path.suffix + '.tags')
    
    # Create a temporary file to store the output
    temp_output_path = Path(f"{file_path}.temp.html")
    
    try:
        with open(temp_output_path, 'w', encoding='utf-8') as f_out:
            postproc_cmd = ['awk', '-v', f'tags={relative_tags_path}', '-f', str(decl_anchors_script)]
            postproc_proc = subprocess.Popen(
                postproc_cmd, 
                stdin=subprocess.PIPE, 
                stdout=f_out, 
                stderr=subprocess.PIPE, 
                text=True, 
                encoding='utf-8'
            )
            _, stderr = postproc_proc.communicate(input=html_content)

            if postproc_proc.returncode != 0:
                raise RuntimeError(f"Awk post-processing failed: {stderr}")
        
        # Read the processed content from the temporary file
        with open(temp_output_path, 'r', encoding='utf-8') as f:
            processed_content = f.read()
        
        return processed_content
    finally:
        # Remove the temporary file
        if temp_output_path.exists():
            temp_output_path.unlink()


def post_process_c_html(html_content: str, file_path: Path, 
                       repo_root: Path, darcsit_dir: Path, docs_dir: Path) -> str:
    """
                       Post-processes HTML generated from C/C++ source files to enhance documentation presentation.
                       
                       This function cleans up and restructures HTML output from C/C++ files by removing extraneous line numbers, wrapping code blocks in container divs for consistent styling, and converting `#include` statements into hyperlinks to either local documentation or the Basilisk source repository. It also removes JavaScript related to dynamic asset paths and inserts a script defining `window.repoName` after the opening `<body>` tag.
                       
                       Args:
                           html_content: HTML content generated from a C/C++ source file.
                           file_path: Path to the original source file.
                           repo_root: Root directory of the repository.
                           darcsit_dir: Directory containing darcsit scripts.
                           docs_dir: Output directory for generated HTML documentation.
                       
                       Returns:
                           The modified HTML content with improved code block styling, linked includes, and repository metadata.
                       """
    # Remove trailing line numbers added by literate-c
    cleaned_html = re.sub(
        r'(\s*(?:<span class="[^"]*">\s*\d+\s*</span>|\s+\d+)\s*)+(\s*</span>)', 
        r'\2', 
        html_content
    )
    
    # Wrap <pre><code> blocks with a container div
    def wrap_pre_code_with_container(match):
        """
        Wrap the matched content in a container div.
        
        This function retrieves the entire match from a regex match object and wraps it
        inside a <div> element with the CSS class "code-block-container". It is used to
        enclose code block elements within an HTML container for consistent styling.
        
        Args:
            match (Match): A regex match object containing the code block to be wrapped.
        
        Returns:
            str: An HTML string with the wrapped code block.
        """
        pre_content = match.group(0)
        return f'<div class="code-block-container">{pre_content}</div>'
    
    cleaned_html = re.sub(
        r'<pre[^>]*><code[^>]*>.*?</code></pre>', 
        wrap_pre_code_with_container, 
        cleaned_html, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Process the sourceCode divs
    def wrap_source_code_with_container(match):
        # Get the div's contents (which includes the pre/code)
        """
        Wraps a matched code block in a container div.
        
        Extracts the content captured by the first group of the provided regex match and
        returns it enclosed in a <div> element with the "code-block-container" class.
        
        Args:
            match (re.Match): A regex match object with the source code block in its first group.
        
        Returns:
            str: An HTML string with the code block wrapped in a container div.
        """
        div_contents = match.group(1)
        # Return the pre/code wrapped in our container div
        return f'<div class="code-block-container">{div_contents}</div>'
    
    # Replace the standard sourceCode div with our container div
    cleaned_html = re.sub(
        r'<div class="sourceCode" id="cb\d+"[^>]*>(.*?)</div>', 
        wrap_source_code_with_container, 
        cleaned_html, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Add links to #include statements
    def create_include_link(match):
        """
        Converts a matched C/C++ #include directive into an HTML hyperlink.
        
        Given a regex match object for an include directive, generates an anchor tag linking to local documentation if the included file exists in the 'src-local' directory, or to the Basilisk source repository otherwise. Preserves the original HTML span formatting of the include statement.
        
        Args:
            match: A regex match object with four groups representing the prefix span, opening span tag, filename, and closing span tag.
        
        Returns:
            An HTML string with the include filename wrapped in a hyperlink to the appropriate documentation or source.
        """
        prefix = match.group(1)  # e.g., <span class="pp">#include </span>
        span_tag_open = match.group(2)  # e.g., <span class="im">
        filename = match.group(3)  # e.g., filename.h or path/filename.h
        span_tag_close = match.group(4)  # </span>
        
        # Reconstruct original full span tag assuming literal quotes
        original_span_tag = f'{span_tag_open}\"{filename}\"{span_tag_close}'
        
        # Split filename by '/' and take the last part for checking in src-local root
        check_filename = filename.split('/')[-1]
        local_file_path = repo_root / 'src-local' / check_filename
        
        if local_file_path.is_file():
            # Link to local generated HTML file
            # Use the new file naming pattern: file.c -> file.c.html, file.h -> file.h.html
            target_html_path = (docs_dir / 'src-local' / check_filename).with_suffix(local_file_path.suffix + '.html')
            # Calculate relative path from the *current* HTML file's directory
            try:
                relative_link = os.path.relpath(target_html_path, start=file_path.parent)
                link_url = relative_link.replace('\\', '/')  # Ensure forward slashes
                # remove /docs/ with / in link
                link_url = link_url.replace('/docs/', '/')
            except ValueError:
                # Handle cases where paths are on different drives (should not happen here)
                link_url = target_html_path.as_uri()  # Fallback to absolute URI
            link_title = f"Link to local documentation for {filename}"
        else:
            # Link to basilisk.fr, preserving original path if present
            link_url = f"http://basilisk.fr/src/{filename}"
            link_title = f"Link to Basilisk source for {filename}"
        
        # Return the prefix span, followed by the link wrapping the filename span
        return f'{prefix}<a href="{link_url}" title="{link_title}">{original_span_tag}</a>'
    
    # Corrected regex: Find pp span followed by im span, allowing flexible space
    # and handle potential HTML entity quotes (&quot;)
    include_pattern = r'(<span class="pp">#include\s*</span>)(<span class=\"im\">)(?:\"|&quot;)(.*?)(?:\"|&quot;)(</span>)'
    cleaned_html = re.sub(include_pattern, create_include_link, cleaned_html, flags=re.DOTALL)
    
    # Remove all JavaScript related to dynamic base path resolution and asset paths
    # This includes both inline scripts and any JS variables or functions related to paths
    cleaned_html = re.sub(r'<script[^>]*>\s*// Dynamic base path resolution.*?</script>', '', cleaned_html, flags=re.DOTALL)
    cleaned_html = re.sub(r'<script[^>]*>\s*// Helper function to create dynamic asset paths.*?</script>', '', cleaned_html, flags=re.DOTALL)
    cleaned_html = re.sub(r'<script[^>]*>\s*window\.basePath\s*=.*?</script>', '', cleaned_html, flags=re.DOTALL)
    cleaned_html = re.sub(r'<script[^>]*>\s*function\s+assetPath.*?</script>', '', cleaned_html, flags=re.DOTALL)
    
    # Add repoName variable to the HTML
    repo_script = f'\n<script>window.repoName = "{REPO_NAME}";</script>\n'
    # Insert after opening body tag
    cleaned_html = re.sub(r'<body[^>]*>', lambda m: m.group(0) + repo_script, cleaned_html)
    
    return cleaned_html


def insert_css_link_in_html(html_file_path: Path, css_path: Path, is_root: bool = True) -> bool:
    """
    Insert a CSS link tag into an HTML file's <head> section.
    
    Reads the specified HTML file and checks whether a <link> tag for the given CSS
    file already exists. If not, it inserts the tag just before the closing </head> tag.
    When the HTML file is in a subdirectory (is_root is False), the CSS file name is 
    prefixed with "../" to ensure the link is correct.
    
    Parameters:
        html_file_path: The path to the target HTML file.
        css_path: The path to the CSS file to be linked.
        is_root: True if the HTML file is in the root directory; otherwise, False.
    
    Returns:
        True if the CSS link was inserted or already exists; otherwise, False.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Define the CSS path - relative to the HTML file
        if is_root:
            css_link = f'<link href="{Path(css_path).name}" rel="stylesheet" type="text/css" />'
        else:
            css_link = f'<link href="../{Path(css_path).name}" rel="stylesheet" type="text/css" />'
        
        # Check if the CSS link is already included
        if 'link href="' + Path(css_path).name + '"' in content or 'link href="../' + Path(css_path).name + '"' in content:
            # CSS link is already included, no need to add it
            return True
        
        # Find the head section to insert the CSS link
        head_end_idx = content.find('</head>')
        if head_end_idx == -1:
            # If no </head> tag found, check if there's a <head> tag
            head_start_idx = content.find('<head>')
            if head_start_idx != -1:
                # Insert after the <head> tag
                modified_content = content[:head_start_idx + 6] + '\n    ' + css_link + content[head_start_idx + 6:]
            else:
                # No head tag, create a complete HTML structure
                debug_print(f"Warning: No head tag found in {html_file_path}, creating complete HTML structure")
                modified_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    {css_link}
</head>
<body>
{content}
</body>
</html>"""
        else:
            # Insert the CSS link tag just before the closing head tag
            modified_content = content[:head_end_idx] + '    ' + css_link + '\n    ' + content[head_end_idx:]
        
        # Write back the modified content
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        return True
    except Exception as e:
        print(f"Error inserting CSS link in {html_file_path}: {e}")
        return False


def insert_javascript_in_html(html_file_path: Path) -> bool:
    """
    Inserts inline JavaScript for copy-to-clipboard on code blocks.
    
    Reads the specified HTML file and checks for an existing copy button script by searching
    for elements with the "copy-button" class. If absent, the function inserts an inline JavaScript
    snippet that adds copy buttons to code block containers. The snippet is placed just before the
    closing </body> tag; if no </body> tag is found, it is appended to the content (or wrapped in a
    basic HTML structure if no <body> tag exists). Returns True if the snippet is inserted or
    already present, and False if updating the file fails.
      
    Args:
        html_file_path: The path to the HTML file to update.
    
    Returns:
        True if the JavaScript snippet is present or successfully inserted; False otherwise.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # JavaScript for copy functionality
        copy_js = '''
    <script type="text/javascript">
    document.addEventListener('DOMContentLoaded', function() {
        // Add copy button to each code block container
        const codeBlocks = document.querySelectorAll('.code-block-container pre');
        codeBlocks.forEach(function(codeBlock, index) {
            // Create button element
            const button = document.createElement('button');
            button.className = 'copy-button';
            button.textContent = 'Copy';
            button.setAttribute('aria-label', 'Copy code to clipboard');
            button.setAttribute('data-copy-state', 'copy');
            
            // Get the code block container (parent of the pre)
            const container = codeBlock.parentNode;
            
            // Add the button to the container
            container.appendChild(button);
            
            // Set up click event
            button.addEventListener('click', function() {
                // Create a textarea element to copy from
                const textarea = document.createElement('textarea');
                // Get the text content from the pre element (the actual code)
                textarea.value = codeBlock.textContent;
                document.body.appendChild(textarea);
                textarea.select();
                
                try {
                    // Execute copy command
                    document.execCommand('copy');
                    // Update button state
                    button.textContent = 'Copied!';
                    button.classList.add('copied');
                    
                    // Reset button state after 2 seconds
                    setTimeout(function() {
                        button.textContent = 'Copy';
                        button.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('Copy failed:', err);
                    button.textContent = 'Error!';
                }
                
                // Clean up
                document.body.removeChild(textarea);
            });
        });
    });
    </script>
        '''
        
        # Check if the JavaScript is already included
        if 'class="copy-button"' in content:
            # JavaScript is already included, no need to add it
            return True
        
        # Find the body end to insert the JavaScript
        body_end_idx = content.find('</body>')
        if body_end_idx == -1:
            # If no </body> tag found, check if there's a <body> tag
            body_start_idx = content.find('<body>')
            if body_start_idx != -1:
                # Insert at the end of the content
                modified_content = content + copy_js
            else:
                # No body tag, create a complete HTML structure
                debug_print(f"Warning: No body tag found in {html_file_path}, creating complete HTML structure")
                modified_content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head>
<body>
{content}
{copy_js}
</body>
</html>"""
        else:
            # Insert the JavaScript code just before the closing body tag
            modified_content = content[:body_end_idx] + copy_js + content[body_end_idx:]
        
        # Write back the modified content
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        return True
    except Exception as e:
        print(f"Error inserting JavaScript in {html_file_path}: {e}")
        return False


def process_file_with_page2html_logic(file_path: Path, output_html_path: Path, repo_root: Path, 
                                     basilisk_dir: Path, darcsit_dir: Path, template_path: Path, 
                                     base_url: str, wiki_title: str, literate_c_script: Path, docs_dir: Path) -> bool:
    """
                                     Converts a source file to HTML and applies file-type-specific post-processing.
                                     
                                     Prepares the source file for Pandoc conversion based on its type, generates HTML output, and applies enhancements tailored to the file format. For Python, shell, Markdown, and Jupyter notebook files, it post-processes the HTML to improve code block presentation and interactivity; for Jupyter notebooks, it also copies the original `.ipynb` file to the documentation directory. For C/C++ files, it applies awk-based processing and further HTML cleanup. Inserts JavaScript for code block copy buttons. Returns True if processing succeeds, otherwise False.
                                     """
    print(f"  Processing {file_path.relative_to(repo_root)} -> {output_html_path.relative_to(repo_root / 'docs')}")

    try:
        # Check if we're processing a Jupyter notebook
        is_jupyter_notebook = file_path.suffix.lower() == '.ipynb'
        
        # For Jupyter notebooks, copy the original .ipynb file to the docs directory
        if is_jupyter_notebook:
            # The destination should be in the same directory as the HTML file
            notebook_dest = output_html_path.parent / file_path.name
            # Copy the notebook file
            try:
                import shutil
                shutil.copy2(file_path, notebook_dest)
                print(f"  Copied notebook {file_path.name} to {notebook_dest.relative_to(repo_root / 'docs')}")
            except Exception as e:
                print(f"  Warning: Failed to copy notebook file: {e}")
        
        # Prepare pandoc input based on file type
        pandoc_input_content = prepare_pandoc_input(file_path, literate_c_script)
        
        # Calculate relative URL path for the page
        # Ensure URL starts with / and uses forward slashes
        page_url = (base_url + output_html_path.relative_to(repo_root / 'docs').as_posix()).replace('//', '/')
        
        # Clean up the page title - remove leading/trailing dashes and spaces
        page_title = file_path.relative_to(repo_root).as_posix().strip('- \t')
        
        # Run pandoc to convert to HTML
        # Add debugging information
        print(f"Processing file: {file_path.name} with REPO_NAME={REPO_NAME}")
        
        # Pass SEO metadata with repository name
        seo_metadata = extract_seo_metadata(file_path, pandoc_input_content)
        
        # Calculate asset path prefix based on output file depth
        asset_path_prefix = calculate_asset_prefix(output_html_path, docs_dir)
        
        pandoc_stdout = run_pandoc(
            pandoc_input_content, 
            output_html_path, 
            template_path, 
            base_url, 
            wiki_title, 
            page_url, 
            page_title,
            asset_path_prefix, # Pass the calculated prefix
            seo_metadata
        )
        
        # Determine file type for post-processing
        is_python_file = file_path.suffix.lower() == '.py'
        is_shell_file = file_path.suffix.lower() == '.sh'
        is_markdown_file = file_path.suffix.lower() == '.md'
        
        # Apply appropriate post-processing based on file type
        if is_python_file or is_shell_file or is_markdown_file or is_jupyter_notebook:
            # For Python, Shell, Markdown, and Jupyter notebook files
            # Read the generated HTML file
            with open(output_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Post-process the HTML
            processed_html = post_process_python_shell_html(html_content)
            
            # Write back the processed HTML
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(processed_html)
        else:
            # For C/C++ files
            # Read the generated HTML file
            with open(output_html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Use awk for post-processing
            processed_html = run_awk_post_processing(html_content, file_path, repo_root, darcsit_dir)
            
            # Further post-process the HTML
            cleaned_html = post_process_c_html(processed_html, file_path, repo_root, darcsit_dir, docs_dir)
            
            # Write back the processed HTML
            with open(output_html_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_html)
        
        # Insert CSS link and JavaScript for all file types
        # CSS link is now handled by the template using asset_path_prefix
        # is_root = output_html_path.parent == docs_dir
        # insert_css_link_in_html(output_html_path, CSS_PATH, is_root) 
        insert_javascript_in_html(output_html_path)
        
        return True
    
    except Exception as e:
        print(f"  Error processing {file_path}: {e}")
        return False


def convert_directory_tree_to_html(readme_content: str) -> str:
    """
    Converts a plain text directory tree in README content into an HTML site map.
    
    This function scans the provided README content for a markdown code block that
    contains a directory tree. If found, it parses the tree structure and transforms it
    into a nested HTML format wrapped in a <div> element with the class "repository-structure".
    Directories and files are converted into bullet list items with hyperlinks where appropriate.
    If no directory tree block is detected, the original content is returned unchanged.
    
    Args:
        readme_content: The complete README file content as a string.
    
    Returns:
        A string with the directory tree section replaced by an HTML site map.
    """
    # Find the directory tree section
    tree_pattern = r'```\s*\n(├.*?\n.*?└.*?)\n```'
    tree_match = re.search(tree_pattern, readme_content, re.DOTALL)
    
    if not tree_match:
        return readme_content  # No tree found, return original content
        
    tree_text = tree_match.group(1)
    
    # Parse the directory tree
    html_structure = ['<div class="repository-structure">']
    
    # Track parent directories and their indentation levels for proper nesting
    path_stack = []
    prev_indent = -1
    
    for line in tree_text.split('\n'):
        # Skip empty lines
        if not line.strip():
            continue
            
        # Determine indentation level based on the structure symbols
        indent_level = 0
        
        if '│   ' in line:
            indent_level = line.count('│   ')
        elif '    ' in line and ('├── ' in line or '└── ' in line):
            # Handle case where │ might be missing but spacing is present
            spaces_before_item = len(line) - len(line.lstrip(' '))
            indent_level = spaces_before_item // 4
        
        # Clean up the line by removing directory tree symbols
        clean_line = line.replace('├── ', '').replace('└── ', '').replace('│   ', '')
        
        # Get the path and description
        parts = clean_line.strip().split(None, 1)
        path = parts[0]
        description = parts[1] if len(parts) > 1 else ''
        
        # Determine if it's a directory or file based on path ending with /
        is_dir = path.endswith('/')
        
        # Update the path stack based on indentation changes
        if indent_level > prev_indent:
            # Going deeper, add the previous item to the stack
            if path_stack and prev_indent >= 0:
                path_stack.append(path_stack[-1])
        elif indent_level < prev_indent:
            # Going up, remove items from stack
            for _ in range(prev_indent - indent_level):
                if path_stack:
                    path_stack.pop()
        
        # Generate proper indentation for HTML output
        indent = '  ' * indent_level
        
        # Generate the HTML list item
        item_html = f"{indent}* "
        
        if is_dir:
            # For directories
            dir_name = path.rstrip('/')
            # Special case for basilisk/src/ which should not be linked
            if dir_name == "basilisk/src":
                item_html += f"**{path}** - {description}"
            else:
                # For other directories, create links
                item_html += f"**[{path}]({dir_name})** - {description}"
            
            # Update the path stack for children
            if len(path_stack) <= indent_level:
                path_stack.append(dir_name)
            else:
                path_stack[indent_level] = dir_name
        else:
            # For files
            # Determine the parent directory path
            parent_path = path_stack[indent_level-1] if indent_level > 0 and path_stack else ""
            
            # Create HTML link with extension preserved in the filename
            file_path = f"{parent_path}/{path}" if parent_path else path
            file_path = file_path.lstrip('/')
            
            # Preserve the original file extension in the link
            # Use the new file naming pattern: file.c -> file.c.html, file.h -> file.h.html
            item_html += f"**[{path}]({file_path}.html)** - {description}"
        
        html_structure.append(item_html)
        prev_indent = indent_level
    
    html_structure.append('</div>')
    
    # Replace the tree section with the HTML structure
    html_tree = '\n'.join(html_structure)
    modified_content = readme_content.replace(tree_match.group(0), html_tree)
    
    return modified_content


def generate_directory_index(directory_name: str, directory_path: Path, generated_files: Dict[Path, Path], docs_dir: Path, repo_root: Path) -> bool:
    """
    Generates an index.html page for a documentation directory listing all generated HTML files.
    
    Creates a landing page for the specified directory using a custom template, displaying a table of contents with links to each documentation file and their descriptions (extracted from meta tags). Assigns CSS classes to file types for styling, formats the directory name for display, and writes the resulting HTML index page. Returns True if the index page is generated successfully, otherwise False.
    """
    try:
        index_path = directory_path / "index.html"
        
        # Filter files in this directory
        directory_files = {}
        for original_path, html_path in generated_files.items():
            if html_path.parent == directory_path and html_path.name != "index.html":
                relative_original_path = original_path.relative_to(repo_root)
                relative_html_path = html_path.relative_to(directory_path)  # Path relative to the directory
                directory_files[html_path] = {
                    "html_path": relative_html_path,
                    "original_path": relative_original_path,
                    "name": relative_original_path.name,  # Use full filename with extension
                    "description": "",  # We'll try to extract descriptions below
                }
                
        # Try to extract descriptions for each file
        for html_path, info in directory_files.items():
            try:
                # Read the HTML file to extract description from meta tags
                html_content = html_path.read_text(encoding='utf-8')
                desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html_content)
                if desc_match:
                    description = desc_match.group(1).strip()
                    # Limit description length for UI
                    if len(description) > 120:
                        description = description[:117] + "..."
                    info["description"] = description
            except Exception as e:
                print(f"Error extracting description from {html_path}: {e}")
        
        # Read the template file
        template_path = TEMPLATE_PATH # Use the temporary processed template
        # Use the custom template for the index pages
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            print(f"Error reading template: {e}")
            return False
            
        # Format the directory name for the title
        formatted_dir_name = directory_name.capitalize()
        if formatted_dir_name == 'Src-local':
            formatted_dir_name = "Local Source Files"
        elif formatted_dir_name == 'Simulationcases':
            formatted_dir_name = "Simulation Cases"  
        elif formatted_dir_name == 'Postprocess':
            formatted_dir_name = "Post-Processing Tools"
            
        # Create the TOC content
        toc_html = f"<h1>{formatted_dir_name}</h1>\n\n"
        
        if directory_files:
            toc_html += '<div class="documentation-section">\n'
            toc_html += '<table class="documentation-files">\n'
            
            # Sort files by name
            sorted_files = sorted(directory_files.values(), key=lambda x: x['original_path'].name.lower())
            
            for info in sorted_files:
                file_extension = info["original_path"].suffix.lower()
                file_type_class = "file-other"
                
                # Assign CSS classes based on file extension
                if file_extension in [".c", ".h"]:
                    file_type_class = "file-c"  # C/header files
                elif file_extension in [".py"]:
                    file_type_class = "file-python"  # Python files
                elif file_extension in [".ipynb"]:
                    file_type_class = "file-jupyter"  # Jupyter notebook files
                    
                file_name = info["name"]  # Use the full filename with extension
                
                toc_html += f'<tr>\n'
                toc_html += f'  <td class="file-icon"><span class="{file_type_class}"></span></td>\n'
                toc_html += f'  <td class="file-link" style="padding-right: 2em;"><a href="{info["html_path"]}" class="doc-link-button">{file_name}</a></td>\n'
                toc_html += f'  <td class="file-desc">{info["description"]}</td>\n'
                toc_html += f'</tr>\n'
                
            toc_html += '</table>\n'
            toc_html += '</div>\n'
        else:
            toc_html += '<p>No documentation files found in this directory.</p>\n'
            
        # Replace template variables
        page_title = f"{formatted_dir_name} | Documentation"
        html_content = template_content
        html_content = html_content.replace("$if(pagetitle)$$pagetitle$$endif$$if(wikititle)$ | $wikititle$$endif$", page_title)
        html_content = html_content.replace("$if(description)$$description$$else$Computational fluid dynamics simulations using Basilisk C framework.$endif$", 
                                          "Documentation for the CoMPhy-Lab computational fluid dynamics framework.")
        html_content = html_content.replace("$if(keywords)$$keywords$$else$fluid dynamics, CFD, Basilisk, multiphase flow, computational physics$endif$", 
                                          f"fluid dynamics, CFD, Basilisk, {directory_name}, documentation")
        # Ensure repo name is shown in folder index pages
        html_content = html_content.replace(
            "$if(reponame)$$reponame$$else$Documentation$endif$", REPO_NAME
        )
        
        # Replace asset prefix based on depth
        asset_path_prefix = calculate_asset_prefix(index_path, docs_dir)
        html_content = html_content.replace("$asset_path_prefix$", asset_path_prefix)
        
        # Handle $if(tabs)$ ... $tabs$ ... $endif$ section
        if "$if(tabs)$" in html_content:
            html_content = re.sub(r'\$if\(tabs\)\$(.*?)\$tabs\$(.*?)\$endif\$', '', html_content, flags=re.DOTALL)
        
        # Replace main content
        content_replacement = toc_html
        html_content = re.sub(r'<div class="page-content">\s*.*?\$body\$.*?</div>', 
                              f'<div class="page-content">\n{content_replacement}\n</div>', 
                              html_content, flags=re.DOTALL)
        
        # Remove any remaining template variables like $base$, $body$ etc.
        html_content = re.sub(r'\$[a-zA-Z0-9_]+\$', '', html_content)
        # Remove conditional blocks like $if(variable)$...$endif$
        html_content = re.sub(r'\$if\([^)]+\)\$.*?\$endif\$', '', html_content, flags=re.DOTALL)
        
        # Clean up the dynamic base path script if it somehow survived
        html_content = re.sub(r'<script[^>]*>\s*// Dynamic base path resolution.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>\s*// Helper function to create dynamic asset paths.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>\s*window\.basePath\s*=.*?</script>', '', html_content, flags=re.DOTALL)
        html_content = re.sub(r'<script[^>]*>\s*function\s+assetPath.*?</script>', '', html_content, flags=re.DOTALL)

        # Write the HTML file
        index_path.write_text(html_content, encoding='utf-8')
        print(f"Generated index page for directory: {directory_name} using custom template")
        return True
        
    except Exception as e:
        print(f"Error generating directory index for {directory_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_title_from_filename(filename: str) -> str:
    """
    Converts a filename to a more readable title by:
    1. Removing file extensions
    2. Replacing dashes and underscores with spaces
    3. Capitalizing words
    
    Args:
        filename: The filename to convert
        
    Returns:
        A more readable title
    """
    # Remove any file extensions (including multiple extensions like .c.html)
    name = filename.split('.')[0]
    
    # Replace dashes and underscores with spaces
    name = name.replace('-', ' ').replace('_', ' ')
    
    # Title case the result (capitalize each word)
    return ' '.join(word.capitalize() for word in name.split())


def generate_index(readme_path: Path, index_path: Path, generated_files: Dict[Path, Path], 
                  docs_dir: Path, repo_root: Path) -> bool:
    """
    Generates an index.html page from README.md by integrating documentation links.
    
    Reads the README file (using a default header if missing) and converts its content to HTML.
    The function appends a section that groups links to generated documentation files based on their
    top-level directory, then uses Pandoc with a specified template and configuration to create
    the final HTML. After conversion, it post-processes the file to adjust code blocks and injects
    CSS and JavaScript for enhanced presentation.
    
    Args:
        readme_path: Path to the README.md file.
        index_path: Destination path for the generated index.html.
        generated_files: Dictionary mapping source file paths to their corresponding generated HTML paths.
        docs_dir: Directory where documentation files are stored.
        repo_root: Root directory of the repository used for computing relative paths.
    
    Returns:
        True if index.html was generated and processed successfully, otherwise False.
    """
    if not readme_path.exists():
        print(f"Warning: README.md not found at {readme_path}")
        readme_content = "# Project Documentation\n"
    else:
        readme_content = readme_path.read_text(encoding='utf-8')
        
    # Convert the directory tree to HTML before generating index
    readme_content = convert_directory_tree_to_html(readme_content)

    # Add documentation links section
    links_markdown = "\n\n## Generated Documentation\n\n"
    
    # Group links by top-level directory (src-local, simulationCases, etc.)
    grouped_links = {}
    for original_path, html_path in generated_files.items():
        relative_html_path = html_path.relative_to(docs_dir)
        relative_original_path = original_path.relative_to(repo_root)
        
        # Handle files in the root directory
        if len(relative_original_path.parts) == 1:  # File is directly in the root
            top_dir = "root"
        else:
            top_dir = relative_original_path.parts[0]
            
        if top_dir not in grouped_links:
            grouped_links[top_dir] = []
        
        # Make sure the html_path has the correct format with preserved extension
        # The html_path already has the correct format (file.c.html, file.h.html, etc.)
        # because we modified the output path construction in the main function
        grouped_links[top_dir].append(f"- [{relative_original_path}]({relative_html_path})")

    # Add a section for files in the root directory
    if 'root' in grouped_links and grouped_links['root']:
        links_markdown += f"### Root Directory\n\n"
        links_markdown += "\n".join(sorted(grouped_links['root']))
        links_markdown += "\n\n"
    
    # Add sections for files in the source directories
    for top_dir in sorted(grouped_links.keys()):
        if top_dir in SOURCE_DIRS:  # Source dirs
            links_markdown += f"### {top_dir}\n\n"
            links_markdown += "\n".join(sorted(grouped_links[top_dir]))
            links_markdown += "\n\n"

    # Append links to the end for simplicity
    final_readme_content = readme_content + links_markdown

    # Convert the combined README + links to HTML for index.html
    print(f"Generating index.html with REPO_NAME={REPO_NAME}")
    
    # For the main index.html, make sure we're using "." as the asset path prefix
    asset_path_prefix = "."
    
    pandoc_cmd = [
        'pandoc',
        '-f', 'markdown+tex_math_dollars+raw_html',  # Use markdown with math extensions
        '-t', 'html5',
        '--standalone',
        '--mathjax',  # Add support for LaTeX math
        '--template', str(TEMPLATE_PATH),
        '-V', f'wikititle={WIKI_TITLE}',
        '-V', f'reponame={REPO_NAME}',  # Add repository name
        '-V', 'base=/',
        '-V', 'notitle=true',  # Don't add an automatic title from filename
        '-V', f'pagetitle={WIKI_TITLE}',
        '-V', f'asset_path_prefix={asset_path_prefix}', # For index.html, prefix is always '.'
        '-o', str(index_path)
    ]

    debug_print(f"  [Debug Index] Target path: {index_path}")
    debug_print(f"  [Debug Index] Command: {' '.join(pandoc_cmd)}")

    process = subprocess.run(pandoc_cmd, input=final_readme_content, text=True, capture_output=True, check=False)

    # Print results unconditionally for debugging
    debug_print(f"  [Debug Index] Pandoc Return Code: {process.returncode}")
    if process.stdout:
        debug_print(f"  [Debug Index] Pandoc STDOUT:\n{process.stdout}")
    if process.stderr:
        debug_print(f"  [Debug Index] Pandoc STDERR:\n{process.stderr}")

    if process.returncode != 0:
        print("Error generating index.html:")
        return False
    
    # Post-process index.html for code blocks
    try:
        with open(index_path, 'r', encoding='utf-8') as f_in:
            index_html_content = f_in.read()
        
        processed_html = post_process_python_shell_html(index_html_content)
        
        with open(index_path, 'w', encoding='utf-8') as f_out:
            f_out.write(processed_html)
            
    except Exception as e:
        print(f"Warning: Failed to process code blocks in {index_path}: {e}")
        # Continue even if processing fails, the base file was generated

    # Insert CSS and JavaScript
    # CSS link is now handled by the template using asset_path_prefix
    # insert_css_link_in_html(index_path, CSS_PATH, True) 
    insert_javascript_in_html(index_path)
    
    return True


def generate_robots_txt(docs_dir: Path) -> bool:
    """
    Generate a robots.txt file to guide search engine crawlers.
    
    Args:
        docs_dir: Directory where documentation files are stored
        
    Returns:
        True if robots.txt was generated successfully
    """
    robots_path = docs_dir / 'robots.txt'
    
    try:
        with open(robots_path, 'w', encoding='utf-8') as f:
            f.write('User-agent: *\n')
            f.write('Allow: /\n\n')
            f.write(f'Sitemap: {BASE_DOMAIN}/sitemap.xml\n')
        
        debug_print(f"Generated robots.txt at {robots_path}")
        return True
        
    except Exception as e:
        print(f"Error generating robots.txt: {e}")
        return False


def generate_sitemap(docs_dir: Path, generated_files: Dict[Path, Path]) -> bool:
    """
    Generate a sitemap.xml file for search engines.
    
    Args:
        docs_dir: Directory where documentation files are stored
        generated_files: Dictionary mapping source files to generated HTML files
        
    Returns:
        True if sitemap was generated successfully
    """
    sitemap_path = docs_dir / 'sitemap.xml'
    
    try:
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            
            # Add the homepage
            f.write('  <url>\n')
            f.write(f'    <loc>{BASE_DOMAIN}/</loc>\n')
            f.write('    <changefreq>weekly</changefreq>\n')
            f.write('    <priority>1.0</priority>\n')
            f.write('  </url>\n')
            
            # Add all generated HTML files
            for _, html_path in generated_files.items():
                relative_path = html_path.relative_to(docs_dir)
                url_path = str(relative_path).replace('\\', '/')
                
                f.write('  <url>\n')
                f.write(f'    <loc>{BASE_DOMAIN}/{url_path}</loc>\n')
                f.write('    <changefreq>monthly</changefreq>\n')
                
                # Higher priority for important files
                if 'index' in url_path or url_path.startswith('src-local/'):
                    f.write('    <priority>0.8</priority>\n')
                else:
                    f.write('    <priority>0.6</priority>\n')
                    
                f.write('  </url>\n')
            
            f.write('</urlset>\n')
        
        debug_print(f"Generated sitemap at {sitemap_path}")
        return True
        
    except Exception as e:
        print(f"Error generating sitemap: {e}")
        return False


def copy_css_file(css_path: Path, docs_dir: Path) -> bool:
    """
    Copies a CSS file to the specified documentation directory.
    
    This function copies the CSS file using shutil.copy2 to preserve file metadata.
    If an error occurs during the copy operation, an error message is printed and the
    function returns False.
    
    Args:
        css_path: The path to the source CSS file.
        docs_dir: The destination directory where the CSS file will be copied.
    
    Returns:
        True if the CSS file was successfully copied; otherwise, False.
    """
    try:
        # Copy CSS file to docs directory
        shutil.copy2(css_path, docs_dir / css_path.name)
        debug_print(f"Copied CSS file to {docs_dir / css_path.name}")
        return True
    except Exception as e:
        print(f"Error copying CSS file: {e}")
        return False


def create_favicon_files(docs_dir: Path, logos_dir: Path) -> bool:
    """
    Create necessary favicon files in the docs/assets/favicon directory.
    
    This function ensures all required favicon files exist in the destination
    directory, creating them if needed from source logo files.
    
    Args:
        docs_dir: The documentation root directory
        logos_dir: Directory containing source logo files
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create favicon directory
        favicon_dir = docs_dir / "assets" / "favicon"
        favicon_dir.mkdir(exist_ok=True)
        
        # Copy any existing favicon files from .github/assets/favicon if it exists
        source_favicon_dir = Path(logos_dir.parent, "favicon")
        if source_favicon_dir.exists() and source_favicon_dir.is_dir():
            for item in source_favicon_dir.glob('*'):
                if item.is_file():
                    shutil.copy2(item, favicon_dir / item.name)
                    debug_print(f"Copied favicon file: {item.name}")
        
        # Create essential favicon files if they don't exist
        favicon_files = [
            "favicon.ico",
            "favicon.svg",
            "apple-touch-icon.png",
            "favicon-96x96.png",
            "site.webmanifest"
        ]
        
        # Check if we have the required logo to create favicons
        logo_file = None
        for potential_logo in ["CoMPhy-Lab.svg", "CoMPhy-Lab-no-name.png", "logoBasilisk_TransparentBackground.png"]:
            if (logos_dir / potential_logo).exists():
                logo_file = logos_dir / potential_logo
                break
        
        if logo_file:
            # Create a basic site.webmanifest if it doesn't exist
            webmanifest_path = favicon_dir / "site.webmanifest"
            if not webmanifest_path.exists():
                with open(webmanifest_path, 'w', encoding='utf-8') as f:
                    f.write('''{
  "name": "CoMPhy Lab",
  "short_name": "CoMPhy",
  "icons": [
    {
      "src": "/assets/favicon/android-chrome-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/assets/favicon/android-chrome-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "theme_color": "#ffffff",
  "background_color": "#ffffff",
  "display": "standalone"
}''')
                debug_print(f"Created site.webmanifest")
        
        return True
    except Exception as e:
        print(f"Error creating favicon files: {e}")
        return False


def copy_assets(assets_dir: Path, docs_dir: Path) -> bool:
    """
    Copy assets from source to destination.
    
    This function copies assets such as CSS, JavaScript, images, etc. from the
    source assets directory to the destination docs directory.
    
    Args:
        assets_dir: The source assets directory
        docs_dir: The destination docs directory
        
    Returns:
        True if successful, False otherwise
    """
    try:
        debug_print(f"Copying assets from {assets_dir} to {docs_dir}")
        
        # Create the assets directory in docs if it doesn't exist
        docs_assets_dir = docs_dir / "assets"
        docs_assets_dir.mkdir(exist_ok=True)
        
        # Copy CSS files
        css_dir = assets_dir / "css"
        docs_css_dir = docs_assets_dir / "css"
        docs_css_dir.mkdir(exist_ok=True, parents=True)
        
        if css_dir.exists():
            for css_file in css_dir.glob("**/*"):
                if css_file.is_file():
                    rel_path = css_file.relative_to(css_dir)
                    dest_path = docs_css_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(css_file, dest_path)
                    debug_print(f"Copied {css_file} to {dest_path}")
        
        # Copy JS files (including search_db.json, command-palette.js, command-data.js)
        js_dir = assets_dir / "js"
        docs_assets_js_dir = docs_assets_dir / "js"
        docs_assets_js_dir.mkdir(exist_ok=True, parents=True)

        # Copy all JS files from .github/assets/js to docs/assets/js
        if js_dir.exists():
            for js_file in js_dir.glob("**/*"):
                if js_file.is_file():
                    rel_path = js_file.relative_to(js_dir)
                    dest_path = docs_assets_js_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    try:
                        shutil.copy2(js_file, dest_path)
                        debug_print(f"Copied {js_file} to {dest_path}")
                    except Exception as e:
                        print(f"Error copying JS file {js_file} to {dest_path}: {e}")
        else:
            debug_print(f"JS assets directory {js_dir} does not exist. Skipping JS copy.")

        # Copy any legacy JS files from docs/js into docs/assets/js, then remove docs/js
        legacy_js_dir = docs_dir / "js"
        if legacy_js_dir.exists() and legacy_js_dir.is_dir():
            for legacy_file in legacy_js_dir.glob("*"):
                if legacy_file.is_file():
                    try:
                        shutil.copy2(legacy_file, docs_assets_js_dir / legacy_file.name)
                        debug_print(f"Migrated legacy JS file {legacy_file} to assets/js/")
                    except Exception as e:
                        print(f"Error migrating legacy JS file {legacy_file}: {e}")
            try:
                for legacy_file in legacy_js_dir.glob("*"):
                    legacy_file.unlink()
                legacy_js_dir.rmdir()
                debug_print("Removed legacy docs/js directory.")
            except Exception as e:
                print(f"Error removing legacy docs/js directory: {e}")

        # Ensure required JS files are present
        required_js = ["search_db.json", "command-palette.js", "command-data.js"]
        for req_file in required_js:
            src_file = js_dir / req_file
            dest_file = docs_assets_js_dir / req_file
            if not dest_file.exists() and src_file.exists():
                try:
                    shutil.copy2(src_file, dest_file)
                    debug_print(f"Explicitly copied {src_file} to {dest_file}")
                except Exception as e:
                    print(f"Error copying required JS file {src_file} to {dest_file}: {e}")
            elif not src_file.exists():
                print(f"Warning: Required JS asset {src_file} not found.")

        # Copy images
        img_dir = assets_dir / "images"
        docs_img_dir = docs_assets_dir / "images"
        
        if img_dir.exists():
            docs_img_dir.mkdir(exist_ok=True, parents=True)
            for img_file in img_dir.glob("**/*"):
                if img_file.is_file():
                    rel_path = img_file.relative_to(img_dir)
                    dest_path = docs_img_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(img_file, dest_path)
                    debug_print(f"Copied {img_file} to {dest_path}")
                    
        # Copy logo files
        logos_dir = assets_dir / "logos"
        docs_logos_dir = docs_assets_dir / "logos"
        
        if logos_dir.exists():
            docs_logos_dir.mkdir(exist_ok=True, parents=True)
            for logo_file in logos_dir.glob("**/*"):
                if logo_file.is_file():
                    rel_path = logo_file.relative_to(logos_dir)
                    dest_path = docs_logos_dir / rel_path
                    dest_path.parent.mkdir(exist_ok=True, parents=True)
                    shutil.copy2(logo_file, dest_path)
                    debug_print(f"Copied {logo_file} to {dest_path}")
        
        # Copy custom CSS to root directory
        if css_dir.exists():
            custom_styles_path = css_dir / "custom_styles.css"
            if custom_styles_path.exists():
                # Also copy to root directory to prevent 404s
                shutil.copy2(custom_styles_path, docs_dir / "custom_styles.css")
                debug_print(f"Copied custom_styles.css to root directory")
        
        # Create favicon files as needed
        logos_dir = assets_dir / "logos"
        if logos_dir.exists():
            create_favicon_files(docs_dir, logos_dir)

        # Copy favicon files to root directory to prevent 404s
        favicon_source_dir = assets_dir / "favicon"
        if favicon_source_dir.exists() and favicon_source_dir.is_dir():
            for fav_file in favicon_source_dir.glob("*"):
                if fav_file.is_file():
                    shutil.copy2(fav_file, docs_dir / fav_file.name)
                    debug_print(f"Copied {fav_file.name} to root directory")

        # Copy Basilisk static JS files (jQuery, plots)
        static_js_dir = DARCSIT_DIR / "static" / "js"
        docs_assets_js_dir = docs_dir / "assets" / "js"
        docs_assets_js_dir.mkdir(exist_ok=True, parents=True)
        if static_js_dir.exists() and static_js_dir.is_dir():
            for js_file in static_js_dir.glob("*.js"):
                try:
                    shutil.copy2(js_file, docs_assets_js_dir / js_file.name)
                    debug_print(f"Copied static js file: {js_file.name} to assets/js/")
                except Exception as e:
                    print(f"Error copying static js file {js_file} to assets/js/: {e}")
        # Remove any old docs/js directory if it exists
        legacy_js_dir = docs_dir / "js"
        if legacy_js_dir.exists() and legacy_js_dir.is_dir():
            try:
                for legacy_file in legacy_js_dir.glob("*"):
                    legacy_file.unlink()
                legacy_js_dir.rmdir()
                debug_print("Removed legacy docs/js directory.")
            except Exception as e:
                print(f"Error removing legacy docs/js directory: {e}")

        return True
    except Exception as e:
        print(f"Error copying assets: {e}")
        return False


def main():
    """
    Generate HTML documentation for the project.
    
    This function orchestrates the documentation generation process by validating
    configuration, setting up the output directories, and copying required CSS files.
    It finds source files in the repository, converts them to HTML using type-specific
    processing logic, and collects the results into a generated files dictionary.
    Finally, it creates an index page and produces SEO-compliant files such as robots.txt
    and sitemap.xml, with all output written to the documentation directory.
    """
    if not validate_config():
        return
    
    try:
        # Create docs directory if it doesn't exist
        DOCS_DIR.mkdir(exist_ok=True)
        
        # If force-rebuild is enabled, clean out the docs directory first
        if FORCE_REBUILD:
            print("\nForce rebuild enabled. Cleaning docs directory...")
            # Only remove HTML files to preserve assets
            for html_file in DOCS_DIR.rglob('*.html'):
                try:
                    html_file.unlink()
                    debug_print(f"Removed {html_file}")
                except Exception as e:
                    print(f"Warning: Could not remove {html_file}: {e}")
        
        # Copy all assets (CSS, JS, logos, fonts, etc.) to docs directory
        print("\nCopying assets...")
        assets_dir = REPO_ROOT / '.github' / 'assets'
        if not copy_assets(assets_dir, DOCS_DIR):
            print("Failed to copy assets.")
            return
        
        # Find all source files
        source_files = find_source_files(REPO_ROOT, SOURCE_DIRS)
        if not source_files:
            print("No source files found.")
            return
        
        # Dictionary to store generated HTML files
        generated_files = {}
        
        # Process each source file
        for file_path in source_files:
            # Determine output path
            relative_path = file_path.relative_to(REPO_ROOT)
            
            # Create output path with file extension preserved in the HTML filename
            # For example: file.c -> file.c.html, file.h -> file.h.html, file.py -> file.py.html
            output_html_path = DOCS_DIR / relative_path.with_suffix(relative_path.suffix + '.html')
            
            # Create output directory if it doesn't exist
            output_html_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip existing files if not forcing rebuild
            if not FORCE_REBUILD and output_html_path.exists():
                print(f"  Skipping existing file: {output_html_path.relative_to(DOCS_DIR)}")
                generated_files[file_path] = output_html_path
                continue
            
            # Process file and generate HTML
            if process_file_with_page2html_logic(
                file_path, 
                output_html_path, 
                REPO_ROOT, 
                BASILISK_DIR, 
                DARCSIT_DIR, 
                TEMPLATE_PATH, 
                BASE_URL, 
                WIKI_TITLE, 
                LITERATE_C_SCRIPT,
                DOCS_DIR
            ):
                generated_files[file_path] = output_html_path
        
        # Generate nice folder index pages for each directory in SOURCE_DIRS
        print("\nGenerating folder index pages...")
        for source_dir in SOURCE_DIRS:
            # Create path to the docs directory for this source dir
            docs_source_dir = DOCS_DIR / source_dir
            if docs_source_dir.exists():
                if not generate_directory_index(source_dir, docs_source_dir, generated_files, DOCS_DIR, REPO_ROOT):
                    print(f"Failed to generate index page for {source_dir}.")
        
        # Always regenerate main index.html
        print("\nGenerating main index.html...")
        if not generate_index(README_PATH, INDEX_PATH, generated_files, DOCS_DIR, REPO_ROOT):
            print("Failed to generate index.html.")
            return
        
        # Generate robots.txt
        print("\nGenerating robots.txt...")
        if not generate_robots_txt(DOCS_DIR):
            print("Failed to generate robots.txt.")
            return
        
        # Generate sitemap
        print("\nGenerating sitemap...")
        if not generate_sitemap(DOCS_DIR, generated_files):
            print("Failed to generate sitemap.")
            return
        
        print("\nDocumentation generation complete.")
        print(f"Output generated in: {DOCS_DIR}")

        # Copy required JS files from basilisk source directly to docs/assets/js for website
        js_src_dir = BASILISK_DIR / 'src' / 'darcsit' / 'static' / 'js'
        js_dest_dir = DOCS_DIR / 'assets' / 'js'
        js_dest_dir.mkdir(parents=True, exist_ok=True)
        for js_file in ['jquery.min.js', 'jquery-ui.packed.js', 'plots.js']:
            src = js_src_dir / js_file
            dst = js_dest_dir / js_file
            if src.exists():
                shutil.copy2(src, dst)
                print(f"Copied Basilisk JS file {src} to {dst}")
            else:
                print(f"Warning: Basilisk JS file {src} not found, could not copy to {dst}")
        
    finally:
        # Clean up temporary template file
        temp_template_path = TEMPLATE_PATH.parent / (TEMPLATE_PATH.stem.replace('.temp', '') + '.temp.html')
        if temp_template_path.exists():
            try:
                temp_template_path.unlink()
                debug_print(f"Cleaned up temporary template file: {temp_template_path}")
            except Exception as e:
                print(f"Warning: Could not delete temporary template file: {e}")


if __name__ == "__main__":
    main()