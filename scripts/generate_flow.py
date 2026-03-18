"""NeonAI: Developer utilities and maintenance scripts."""

import os
import ast
from collections import defaultdict

def analyze_directory(directory="."):
    """Scans all Python files in the directory and extracts imports/functions."""
    modules = {}
    external_imports = set()
    internal_imports = defaultdict(set)
    function_definitions = defaultdict(list)
    class_definitions = defaultdict(list)
    
    internal_bases = ['tools', 'voice', 'web', 'utils', 'models', 'brain', 'exam', 'movie', 'scripts', 'server']

    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'venv', '.env', '.git', 'dist', 'build', '.gemini']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, directory)
                module_name = rel_path.replace(os.sep, '.')[:-3]
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read(), filename=filepath)
                        
                    modules[module_name] = filepath
                    
                    for node in ast.walk(tree):
                        # Extract imports
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                base_module = name.name.split('.')[0]
                                if base_module in internal_bases:
                                    internal_imports[module_name].add(name.name)
                                else:
                                    external_imports.add(base_module)
                                    
                        elif isinstance(node, ast.ImportFrom):
                            if node.level > 0:
                                # Handling relative imports like "from . import X"
                                parts = module_name.split('.')
                                base_pkg = '.'.join(parts[:-node.level]) if node.level <= len(parts) else ""
                                if node.module:
                                    resolved = f"{base_pkg}.{node.module}" if base_pkg else node.module
                                else:
                                    resolved = base_pkg
                                if resolved:
                                    internal_imports[module_name].add(resolved)
                                    
                            elif node.module:
                                base_module = node.module.split('.')[0]
                                if base_module in internal_bases:
                                    # If it's something like "from utils import network", the dependency is on utils or utils.network
                                    # We'll just record the module path
                                    internal_imports[module_name].add(node.module)
                                    # Also record the specific names if they might be submodules
                                    for name in node.names:
                                        internal_imports[module_name].add(f"{node.module}.{name.name}")
                                else:
                                    external_imports.add(base_module)
                        
                        # Extract functions
                        elif isinstance(node, ast.FunctionDef):
                            function_definitions[module_name].append(node.name)
                            
                        # Extract classes
                        elif isinstance(node, ast.ClassDef):
                            class_definitions[module_name].append(node.name)
                            
                except Exception as e:
                    print(f"Warning: Could not parse {filepath}: {e}")

    return {
        "modules": list(modules.keys()),
        "external_deps": sorted(list(external_imports)),
        "internal_deps": dict(internal_imports),
        "functions": dict(function_definitions),
        "classes": dict(class_definitions)
    }

def generate_mermaid_flowchart(analysis):
    """Generates a Mermaid.js flowchart string from the analysis data."""
    lines = ["graph TD"]
    lines.append("    subgraph External Dependencies")
    for ext in analysis["external_deps"][:10]: # Limit to top 10 for readability
        lines.append(f"        ext_{ext.replace('.', '_')}[{ext}]")
    if len(analysis["external_deps"]) > 10:
        lines.append("        ext_more[...] ")
    lines.append("    end")
    
    # Add nodes for all modules
    for module in analysis["modules"]:
        safe_name = module.replace('.', '_')
        label = module.split('.')[-1]
        
        # Add a little detail if there are classes
        if module in analysis["classes"]:
            classes = ", ".join(analysis["classes"][module][:2])
            if classes:
                 label += f"\\n({classes})"
            
        lines.append(f"    {safe_name}[\"{label}\"]")

        
    # Add edges for internal dependencies
    added_edges = set()
    for source, targets in analysis["internal_deps"].items():
        safe_source = source.replace('.', '_')
        for target in targets:
            # check which actual modules this target matches
            for m in analysis["modules"]:
                # If the target is an exact match (e.g. 'utils.network')
                # OR if the target is a parent package (e.g. target is 'utils' and m is 'utils.network')
                # OR if the target is a specific function inside the module (e.g. target is 'utils.network.fetch_data' and m is 'utils.network')
                if m == target or m.startswith(target + ".") or target.startswith(m + "."):
                    safe_target = m.replace('.', '_')
                    if safe_source != safe_target:
                        edge = f"{safe_source} --> {safe_target}"
                        if edge not in added_edges:
                            lines.append(f"    {edge}")
                            added_edges.add(edge)

    return "\n".join(lines)


def generate_markdown_report(analysis):
    """Generates a structured text report."""
    report = "# Python Project Code Flow Analysis\n\n"
    
    report += "## 📦 Modules Discovered\n"
    for mod in sorted(analysis["modules"]):
        report += f"- `{mod}`\n"
        
    report += "\n## 🔗 Internal Dependencies\n"
    for mod, deps in sorted(analysis["internal_deps"].items()):
        report += f"**`{mod}`** imports from:\n"
        # Only show dependencies that actually map to known modules
        valid_deps = set()
        for dep in deps:
            for m in analysis["modules"]:
                if m == dep or m.startswith(dep + ".") or dep.startswith(m + "."):
                    valid_deps.add(m)
        
        for dep in sorted(valid_deps):
            if dep != mod:
                report += f"  - `{dep}`\n"
            
    report += "\n## 🧩 Key Architecture Features\n"
    report += f"- Found **{len(analysis['modules'])}** Python files.\n"
    
    all_funcs = sum(len(funcs) for funcs in analysis['functions'].values())
    report += f"- Found **{all_funcs}** functions across the project.\n"
    
    all_classes = sum(len(cls) for cls in analysis['classes'].values())
    report += f"- Found **{all_classes}** classes.\n"

    report += "\n## 📊 Mermaid Diagram\n"
    report += "*(Paste this into [Mermaid Live Editor](https://mermaid.live/) to see the diagram)*\n\n"
    report += "```mermaid\n"
    report += generate_mermaid_flowchart(analysis)
    report += "\n```\n"

    return report

if __name__ == "__main__":
    print("Analyzing codebase in current directory...")
    # Target the project root assuming the script runs from within NeonAI
    target_dir = r"d:\NeonAI" 
    
    if not os.path.exists(target_dir):
        print(f"Target directory {target_dir} not found. Running in current directory.")
        target_dir = "."
        
    data = analyze_directory(target_dir)
    
    report_content = generate_markdown_report(data)
    
    output_file = os.path.join(target_dir, "code_flow_report.md")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
        
    print(f"\nAnalysis complete! Report saved to: {output_file}")
