**Course**: ECE/CS 598 AL1

**Group**: McKenzy Heavlin, Patrick Marschoun

**How to Run with MITM**
1. Start the Water Tank: `python3 waterTank.py dt.json`
2. Start the MITM: `python3 mitm_async.py`
3. Start the Client: `python3 client_async.py -c tcp -p 5030 dt.json`

**How to Run without MITM**
1. Start the Water Tank: `python3 waterTank.py dt.json`
3. Start the Client: `python3 client_async.py -c tcp -p 5020 dt.json`