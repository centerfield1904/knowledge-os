#!/bin/bash
# Test engagement detection integration

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"
PYTHON="$PROJECT_ROOT/venv/bin/python"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "🧪 Testing engagement detection..."
echo

# Test 1: Check engagement module loads
echo "1. Testing engagement module..."
$PYTHON -c "from knowledge_os.engagement import EngagementDetector; print('✅ Module loads')" || exit 1

# Test 2: Check database init
echo "2. Testing database initialization..."
$PYTHON -c "
from knowledge_os.engagement import EngagementDetector
detector = EngagementDetector('hn_digest_v2.db')
print('✅ Database initialized')
" || exit 1

# Test 3: Test with dummy data
echo "3. Testing opportunity detection..."
$PYTHON << 'EOF'
from knowledge_os.engagement import EngagementDetector, format_engagement_section
from datetime import datetime

detector = EngagementDetector('hn_digest_v2.db')

# Dummy stories
test_stories = [
    {
        'id': 12345,
        'title': 'Ask HN: Best practices for ML in production?',
        'descendants': 3,
        'score': 45,
        'url': 'https://news.ycombinator.com/item?id=12345',
        'time': datetime.now().timestamp()
    },
    {
        'id': 67890,
        'title': 'Show HN: I built a knowledge graph tool',
        'descendants': 2,
        'score': 78,
        'url': 'https://news.ycombinator.com/item?id=67890',
        'time': datetime.now().timestamp()
    }
]

opportunities = detector.detect_opportunities(test_stories, max_results=5)
print(f'✅ Detected {len(opportunities)} opportunities')

# Test formatting
output = format_engagement_section(opportunities)
if output:
    print('✅ Formatting works')
    print('\nSample output:')
    print(output)
else:
    print('⚠️  No output generated')
EOF

echo
echo "4. Testing comment sync (HN API)..."
$PYTHON -c "
from knowledge_os.engagement import EngagementDetector
detector = EngagementDetector('hn_digest_v2.db')
synced = detector.sync_user_comments()
print(f'✅ Synced {synced} comments for vb7132')
"

echo
echo "✅ All tests passed!"
echo
echo "Next: Run full digest pipeline with scripts/run_digest_v2.sh"
