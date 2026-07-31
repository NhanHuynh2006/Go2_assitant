echo "=== xac nhan mic con o card nao + chinh gain lai cho chac ==="
cat /proc/asound/cards | grep -B1 CS202
CARD=$(python3 -c "
import sounddevice as sd
for i,d in enumerate(sd.query_devices()):
    if 'CS202' in d['name']:
        print(d['name'].split('hw:')[1].split(',')[0])
        break")
echo "card hien tai: $CARD"
amixer -c $CARD sset 'Mic' 25%
amixer -c $CARD sget 'Mic'
