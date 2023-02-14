FOOLED_VALUE="100000"
CORRECT_VALUE="3"

INIT_VALUE=`caget -t BL03I-EA-FDBK-01:THRESHOLDPC_XBPM2`

if [ $INIT_VALUE = $CORRECT_VALUE ]
then
    echo "Correct value found, setting to value to fool BPM"
    caput BL03I-EA-FDBK-01:THRESHOLDPC_XBPM2 $FOOLED_VALUE
else
    echo "Fooled value found, setting to correct value"
    caput BL03I-EA-FDBK-01:THRESHOLDPC_XBPM2 $CORRECT_VALUE    
fi