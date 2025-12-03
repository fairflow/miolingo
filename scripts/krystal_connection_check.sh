#!/bin/bash
# Run this script on the Krystal server after SSH login
# to check and kill stale MySQL/SSH connections

echo "🔍 Checking for MySQL connections..."
echo "=================================="

# Check MySQL connections
if command -v mysql &> /dev/null; then
    echo "MySQL connections from localhost:"
    mysql -u fairtlou_miolingo_matthew -p'jam_dgf5quf9gzk*APQ' fairtlou_miolingo -e "SHOW PROCESSLIST;" 2>/dev/null
    echo ""
fi

# Check TCP connections to MySQL port
echo "TCP connections to MySQL port 3306:"
netstat -an | grep :3306 | grep ESTABLISHED | wc -l
echo ""

# Show all connections to port 3306
echo "Detailed MySQL connections:"
netstat -anp 2>/dev/null | grep :3306 | grep ESTABLISHED || netstat -an | grep :3306 | grep ESTABLISHED
echo ""

# Check SSH connections
echo "Current SSH sessions:"
who
echo ""

echo "✅ Check complete"
echo ""
echo "To kill MySQL connections from MySQL side:"
echo "  mysql -u fairtlou_miolingo_matthew -p'jam_dgf5quf9gzk*APQ' fairtlou_miolingo"
echo "  Then run: SHOW PROCESSLIST;"
echo "  Then run: KILL <connection_id>; for each stale connection"
