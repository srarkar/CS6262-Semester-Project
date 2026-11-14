Motivation: (1-2 sentences) 
Advanced Persistent Threats (APTs) are notoriously difficult to track. Often backed by nation states and geared with engineering prowess, APTs have the ability to quickly adapt their behavior to responses from security teams, rotating domains and clearing their tracks behind them. 
One of the most promising techniques for quickly identifying and combating these threat actors is infrastructure pivoting through passive DNS. The idea behind this approach is that attackers do not have unlimited resources. APTs often reuse infrastructure, meaning domains resolving to IPs in clusters associated in the past with an APT serve as prime candidates for additional malicious infrastructure. 
Prior Work: (2 sentences)	
Passive DNS has been used for over a decade to identify malicious domains [4], [2], and specifically for APT detection from enterprise DNS logs [3], [5]. Most relevant, Avgetidis et al. [1] built Atropos to label historical DNS records of APT domains as actor controlled, studied 405 actors over a decade, and recovered 3.06x more actor-utilized IP infrastructure than public threat reports contain. Beyond purely passive collection, Validin has introduced "forward DNS," which proactively generates DNS queries to capture resolutions that passive sensors never observe. Over the course of the semester, we will examine how passive and forward DNS data can be combined for APT infrastructure discovery, with the goal of implementing our own simple pivoting tool.
[1] Avgetidis, A., Faulkenberry, A., Adjibi, V., Galloway, T., Kintis, P., Alrawi, O., ... & Antonakakis, M. (2025, October). From concealment to exposure: Understanding the lifecycle and infrastructure of apt domains. In 2025 28th International Symposium on Research in Attacks, Intrusions and Defenses (RAID) (pp. 488-505). IEEE. https://tillsongalloway.com/Atropos_Final.pdf
[2] Bilge, L., Kirda, E., Kruegel, C., & Balduzzi, M. (2011). EXPOSURE: Finding malicious domains using passive DNS analysis [Conference paper]. Network and Distributed System Security Symposium (NDSS 2011), San Diego, CA, United States. https://www.ndss-symposium.org/wp-content/uploads/2017/09/bilg.pdf
[3] Oprea, A., Li, Z., Yen, T.-F., Chin, S. H., & Alrwais, S. (2015). Detection of early-stage enterprise infection by mining large-scale log data. In 2015 45th Annual IEEE/IFIP International Conference on Dependable Systems and Networks (pp. 45–56). IEEE. https://arxiv.org/pdf/1411.5005
[4] Weimer, F. (2005). Passive DNS replication [Conference paper]. 17th Annual FIRST Conference on Computer Security Incident Handling, Singapore. https://www.enyo.de/fw/software/dnslogger/first2005-interactive.pdf
[5] Zhao, G., Xu, K., Xu, L., & Wu, B. (2015). Detecting APT malware infections based on malicious DNS and traffic analysis. IEEE Access, 3, 1132–1142. https://doi.org/10.1109/ACCESS.2015.2458581
Approach: (4-6 sentences)
Following a measurement methodology rather than an attack-focused one, as our project primarily focuses on gathering data and matching specific APTs/organizations to network activity patterns.
Collect DNS record history across multiple record types (including IPv4, IPv6, name servers, and mail servers) using platforms like Validin (across multiple years)
Group network activity to create digital fingerprints
Match fingerprints to habits that indicate existence of Advanced Persistent Threats (APTs)
Leverage existing fingerprints and run on new DNS activity to catch newly created attacker infrastructure 
Compare fingerprints to known APT threat reports to gauge detection accuracy or prompt re-evaluation of fingerprinting pattern creation
Track how fingerprints evolve over time, such as aging domains to avoid detection, dns resolution lifespan (i.e how long does a dns point to an IP), etc.
Implement a basic pivoting script that allows for us to input a seed domain or IP and then output / track what infrastructure is related to it.
Implement a scoring metric that shows the confidence of identifying APTs, rather than a simple yes or no. This allows for our classification to be more nuanced with more informed decisions


Following a measurement-driven methodology rather than an attack-focused one, our project focuses on empirical data collection to match Advanced Persistent Threat (APT) groups to distinct network activity patterns. Using platforms like Validin, we will collect multi-year DNS records across diverse types, such as IPv4, IPv6, authoritative name servers, and mail exchangers. We will then aggregate these resolution patterns into digital infrastructure fingerprints based on recurring actor behaviors and deployment habits. By executing these fingerprints on incoming DNS streams, our system proactively surfaces newly provisioned threat infrastructure before it appears in public feeds. Finally, we will benchmark our discoveries against verified APT threat reports to evaluate detection accuracy and iteratively refine our fingerprinting heuristics.


Concluding Comments (0-2 sentences)
