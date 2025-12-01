#!/bin/bash
# Check for stale SSH tunnel processes to miolingo.io
# Run this to diagnose SSH tunnel resource leaks

echo "🔍 Checking for SSH tunnel processes to miolingo.io..."
echo ""

# Count SSH processes to miolingo.io
ssh_count=$(ps aux | grep -i "ssh.*miolingo.io\|ssh.*valerii-lon.krystal.uk" | grep -v grep | wc -l | tr -d ' ')

if [ "$ssh_count" -eq 0 ]; then
    echo "✅ No SSH tunnel processes found (clean state)"
else
    echo "⚠️  Found $ssh_count SSH tunnel processes:"
    echo ""
    ps aux | grep -i "ssh.*miolingo.io\|ssh.*valerii-lon.krystal.uk" | grep -v grep | awk '{print "   PID: " $2 " | Started: " $9 " | Command: " substr($0, index($0,$11))}'
    echo ""
    echo "💡 If you see many old processes, you may have tunnel leaks."
    echo "   Run: ps aux | grep -i 'ssh.*miolingo.io' | grep -v grep | awk '{print \$2}' | xargs kill"
    echo "   to clean them up."
fi

echo ""
echo "🔍 Checking Python processes using SSH tunneling..."
echo ""

# Count Python processes that might be running Streamlit with SSH tunnels
python_ssh_count=$(ps aux | grep -i "python.*streamlit\|streamlit.*app.py\|streamlit.*miolingo-admin.py" | grep -v grep | wc -l | tr -d ' ')

if [ "$python_ssh_count" -eq 0 ]; then
    echo "✅ No Streamlit processes found"
else
    echo "📊 Found $python_ssh_count Streamlit processes:"
    echo ""
    ps aux | grep -i "python.*streamlit\|streamlit.*app.py\|streamlit.*miolingo-admin.py" | grep -v grep | awk '{print "   PID: " $2 " | Started: " $9 " | Command: " substr($0, index($0,$11))}'
fi

echo ""
echo "✅ Diagnostic complete"
