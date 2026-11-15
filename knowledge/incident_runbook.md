# Sentinel Demo Co. Incident Runbook (excerpt)

## Severity levels
Critical: an attacker may be inside, customer data is at risk, or the main website is down. Page the on-call engineer now.
Warning: an attack is going on but nobody got in, or errors are high but the service still works. Open a ticket today.
OK: normal noise. No action.

## SSH brute-force attack
Signs: one IP address fails to log in many times in a few minutes, often trying usernames like root, admin, test, oracle.
First steps: page the on-call engineer and confirm that no attacking IP logged in successfully.
Blocking IP addresses on the firewall needs approval from the on-call lead, because a wrong block can cut off real users.
Long-term fix: turn off password login for SSH and allow SSH keys only (needs approval, planned change).

## Attacker logged in
If an attacking IP logged in successfully, treat it as Critical.
Disconnect the server from the network, reset the password of that user, and keep the logs for investigation.
Every one of these steps needs approval from the security lead.

## Web server error storm
Signs: many error lines in the web server log, or a sudden spike of errors in one minute.
First steps: check the most common error message, check the last deployment, and restart the failing worker if needed.
Rolling back a deployment needs approval from the on-call lead.

## Communication
Write a short status update for the team: what happened, what is affected, what was done, what is next.
