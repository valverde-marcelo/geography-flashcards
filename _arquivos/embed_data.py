"""
Embeds data.json into index.html as an inline JS variable.
Safe to run multiple times (idempotent).
"""
import json, re

with open('data.json', encoding='utf-8') as f:
    data = json.load(f)

inline_data = json.dumps(data, ensure_ascii=False)

with open('index.html', encoding='utf-8') as f:
    html = f.read()

# 1. Trim anything accidentally appended after </html>
end_tag = html.rfind('</html>')
html = html[:end_tag + 7] + '\n'

# 2. Remove any existing embedded allData block (handles re-runs)
block_pattern = re.compile(
    r'[ \t]*//[^\n]*embedded inline[^\n]*\n[ \t]*const allData = \[.*?\];\n',
    re.DOTALL
)
html = block_pattern.sub('', html)

# 3. Insert fresh block right after the sortDir declaration
insert_marker = "  let sortDir = 1; // 1 = asc, -1 = desc\n"
replacement = (
    insert_marker
    + "\n"
    + "  // data embedded inline — no server required\n"
    + "  const allData = " + inline_data + ";\n"
)
html = html.replace(insert_marker, replacement, 1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

count = len(re.findall(r'const allData', html))
print(f'Done. index.html updated with inline data ({count} allData declaration).')
