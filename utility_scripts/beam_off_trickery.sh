FOOLED_VALUE="100000"
INIT_VALUE=`caget -t BL03I-EA-FDBK-01:THRESHOLDPC_XBPM2`

trap "caput BL03I-EA-FDBK-01:THRESHOLDPC_XBPM2 $INIT_VALUE" EXIT HUP

echo "Correct value found, setting to value to fool BPM"
caput BL03I-EA-FDBK-01:THRESHOLDPC_XBPM2 $FOOLED_VALUE

echo "Will set back to $INIT_VALUE on termination"

sleep infinity
