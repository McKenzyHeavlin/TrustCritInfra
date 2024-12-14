#!/bin/bash

{
for delta in 0 20 40 60 80 100 200 300 400 500 750 1000; do
    for trial in 0 1 2 3 4; do
        python3 waterTank.py dt.json &
        sleep $((1 + $RANDOM % 7))
        python3 mitm_async.py &
        sleep $((1 + $RANDOM % 17))
        python3 client_async.py -c tcp -p 5030 --file dt.json --delta $delta
        kill $(jobs -p)
    done
done
} ||
{
    kill $(jobs -p)
}




