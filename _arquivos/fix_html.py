import json, re

with open('data.json', encoding='utf-8') as f:
    data = json.load(f)

inline_data = json.dumps(data, ensure_ascii=False)

with open('index.html', encoding='utf-8') as f:
    html = f.read()

# 1. Trim everything after </html>
end = html.rfind('</html>')
html = html[:end + 7] + '\n'

# 2. Remove ALL existing embedded allData blocks (may be duplicated)
block_pattern = re.compile(
    r'[ \t]*//[^\n]*embedded inline[^\n]*\n[ \t]*const allData = \[.*?\];\n',
    re.DOTALL
)
html = block_pattern.sub('', html)

# 3. Remove any leftover lone 'const allData' lines (safety)
html = re.sub(r'[ \t]*const allData = \[.*?\];\n', '', html, flags=re.DOTALL)

# 4. Re-insert clean block in the right place (after sortDir declaration)
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

# Verify
with open('index.html', encoding='utf-8') as f:
    h2 = f.read()

count = len(re.findall(r'const allData', h2))
tail  = h2[h2.rfind('</html>') + 7:].strip()

print(f"const allData occurrences : {count}")
print(f"Content after </html>     : {repr(tail[:60]) if tail else '(none)'}")
print(f"File size                 : {len(h2):,} chars")
