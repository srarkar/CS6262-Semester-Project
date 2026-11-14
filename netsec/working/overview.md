Overview
- We will build a proof-of-concept APT infrastructure pivoting tool, similar to Validin, in two weeks, running on realistic synthetic DNS data. Given one seed domain or IP, the tool returns related infrastructure ranked by a confidence score, with the evidence behind each result.

- Data: a simulator generates a fake DNS world (benign hosting, CDNs, parking, sinkholes) with a few planted "APT actors" whose behavior is modeled on the Atropos paper. Because we plant the actors, we know the ground truth and can measure accuracy exactly.
- Pipeline: simulate → filter noise → pivot → score → evaluate and demo.
- Storage: plain JSON / JSON Lines files in the repo. No database.
- Scope: PoC for class. We make no claims about real APT behavior. The presentation says plainly that the data is simulated and based on published findings.

Basically: 
- Spoof some DNS data to work with with an agreed-upon storage format, plant several known bad actors with some fingerprinting information, develop potential pivoting approaches to discover related infrastructure + benchmark 
- Fill in the gaps when presenting by discussing where things like atropos can fill in the gap (i.e. how real data would be collected for this tooling) 

- Estimated Work Distribution: 
- Need to agree on shared data formats for spoofed records + pivoting engine output
1) Initial data seeding (Jason): Probably 1 person <- can also be the one who decides on the shared data format
2) Filtering: Probably want to put in some noise to replicate general DNS query data, implement some way to filter to find APTs (could be also just spoofed, imagine we’re pulling from virustotal or something) 
3) Pivoting engine (Rick/Suraj/Andrew): Have a couple people (2-3) come up with different approaches
4) Benchmarking (Johnny): One person develops a simple benchmarking script that makes visualizations and stuff 
