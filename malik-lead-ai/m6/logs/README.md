# M6 logs directory

Reserved for M6 run artifacts. By default M6 writes its append-only run log to:

    ../../output/m6_outreach.log

Override with `python3 main.py outreach-execute --log-file <path>`.
Nothing is committed into this directory by default; it only exists to keep
M6's logging location explicit and separate from M1–M5 outputs.
