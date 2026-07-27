import codecs
with codecs.open('pytest_out.txt', 'r', 'utf-16le') as f:
    content = f.read()
with codecs.open('pytest_out_utf8.txt', 'w', 'utf-8') as f:
    f.write(content)
