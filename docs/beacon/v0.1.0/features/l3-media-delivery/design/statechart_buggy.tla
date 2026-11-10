---- MODULE statechart_buggy ----
EXTENDS Naturals, TLC

VARIABLES status, uploads, inFlight, responded

vars == <<status, uploads, inFlight, responded>>

Init == status = "idle" /\ uploads = 0 /\ inFlight = 0 /\ responded = "none"

Req == status = "idle" /\ status' = "loading" /\ inFlight' = 1
       /\ UNCHANGED <<uploads, responded>>

ReqConcurrent == status = "loading" /\ inFlight' = inFlight + 1
       /\ UNCHANGED <<status, uploads, responded>>

Finish == status = "loading" /\ uploads' = uploads + 1
       /\ inFlight' = 0 /\ UNCHANGED <<status, responded>>

Return == status = "cached" /\ responded = "none" /\ responded' = "id"
       /\ UNCHANGED <<status, uploads, inFlight>>

Expire == status = "cached" /\ status' = "expired" /\ responded' = "none"
       /\ UNCHANGED <<uploads, inFlight>>

ReqExpired == status = "expired" /\ responded' = "expired"
       /\ UNCHANGED <<status, uploads, inFlight>>

Next == Req \/ ReqConcurrent \/ Finish \/ Return \/ Expire \/ ReqExpired

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

TypeInvariant == uploads \in 0..2 /\ inFlight \in 0..2

NoDoubleUpload == uploads <= 1
IDsOnlyAfterUpload == responded = "id" => uploads >= 1
ExpiredNoStaleID == status = "expired" => responded /= "id"

====
