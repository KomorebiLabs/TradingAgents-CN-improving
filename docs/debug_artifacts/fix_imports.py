"""Fix imports in copied app.py."""
import re

content = open('app.py', encoding='utf-8').read()
# Fix cli. imports to relative
content = content.replace('from cli.models', 'from .models')
content = content.replace('from cli.utils import', 'from .utils import')
content = content.replace('from cli.announcements', 'from .announcements')
content = content.replace('from cli.stats_handler', 'from .stats_handler')
# static path stays the same (Path(__file__).parent / "static")
open('app.py', 'w', encoding='utf-8').write(content)
print('Fixed imports in app.py')
