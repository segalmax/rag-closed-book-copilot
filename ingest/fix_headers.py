import re
from pathlib import Path

KB_DIR = Path(__file__).parent.parent / "kb" / "raw"

def fix_headers():
    files = list(KB_DIR.rglob("*.md"))
    print(f"Found {len(files)} markdown files.")

    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split('\n')
        new_lines = []
        
        # Skip frontmatter
        in_frontmatter = False
        if lines[0].strip() == "---":
            in_frontmatter = True
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Handle frontmatter toggling
            if i > 0 and stripped == "---" and in_frontmatter:
                in_frontmatter = False
                new_lines.append(line)
                continue
            
            if in_frontmatter:
                new_lines.append(line)
                continue

            # Skip existing headers
            if stripped.startswith("#"):
                new_lines.append(line)
                continue
            
            # Skip code blocks
            if stripped.startswith("```"):
                new_lines.append(line)
                continue

            # Heuristic for headers:
            # 1. Short (< 80 chars)
            # 2. Starts with Capital letter
            # 3. No ending punctuation (., :, ;)
            # 4. Surrounded by empty lines (or start/end of file)
            # 5. Not a list item
            
            if not stripped:
                new_lines.append(line)
                continue

            is_candidate = (
                len(stripped) < 80
                and stripped[0].isupper()
                and not stripped.endswith(('.', ':', ';', ','))
                and not stripped.startswith(('-', '*', '1.', '>', '#', '`'))
                and "http" not in stripped
                and "Watch Video" not in stripped
                and "scraped_at" not in stripped
            )
            
            if is_candidate:
                # Check surrounding lines for emptiness
                # We need to look at the original lines array
                prev_empty = (i == 0) or (lines[i-1].strip() == "")
                next_empty = (i == len(lines) - 1) or (lines[i+1].strip() == "")
                
                if prev_empty and next_empty:
                    # It's likely a header!
                    new_lines.append(f"## {stripped}")
                    # print(f"[{file_path.name}] Converted: '{stripped}'")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Write back
        file_path.write_text("\n".join(new_lines), encoding="utf-8")

if __name__ == "__main__":
    fix_headers()
