# Deploying to AWS (one EC2 server)

Everything runs on one Ubuntu server with Docker. Accounts, tickets, documents and the vector index live in a
Docker volume on the server's disk, so they survive restarts and rebuilds.

## 1. Launch the server (AWS Console > EC2 > Launch instance)
- Region: pick one close to your users (e.g. Mumbai, ap-south-1)
- Image: Ubuntu Server 24.04 LTS
- Type: t3.small minimum (2 GB RAM); t3.medium is more comfortable. t3.micro/t2.micro is too small.
- Key pair: create one and keep the .pem file safe
- Storage: 20 GB gp3
- Security group (the firewall):
  - SSH (22): source = My IP
  - HTTP (80): source = My IP for a private demo, or Anywhere if the demo must be public
  - HTTPS (443): only if you will use a domain, same source choice
- After launch: EC2 > Elastic IPs > allocate and associate it, so the address doesn't change on restart

## 2. Install Docker (on the server)
    ssh -i yourkey.pem ubuntu@<ELASTIC_IP>
    sudo apt update && sudo apt install -y docker.io docker-compose-v2
    sudo usermod -aG docker $USER
    exit        # log in again so the group change applies

## 3. Copy the project (from your computer)
    scp -i yourkey.pem -r kb-assistant ubuntu@<ELASTIC_IP>:~/

## 4. Configure (on the server)
    cd ~/kb-assistant
    cp .env.example .env
    nano .env          # set GROQ_API_KEY, MODEL, and optionally DEMO_PASSWORD
    chmod 600 .env

## 5. Start
    docker compose up -d --build
    docker compose logs -f app       # Ctrl+C to leave the logs

Open http://<ELASTIC_IP> (employees) and http://<ELASTIC_IP>/reviewer (reviewers).
Demo accounts: alice, bob, hana, dev (employees), rita (reviewer). Password: DEMO_PASSWORD, or demo1234 if empty.

## 6. HTTPS with a domain (optional, recommended)
1. Create a DNS A record: demo.yourdomain.com -> your Elastic IP
2. In .env set:  SITE_ADDRESS=demo.yourdomain.com  and  COOKIE_SECURE=1
3. Make sure port 443 is open in the security group
4. docker compose up -d
Caddy fetches and renews the certificate automatically.
Do not set COOKIE_SECURE=1 without HTTPS: logins will silently fail.

## Day-to-day
- Update after changing code:  copy files again, then  docker compose up -d --build
- Logs:                        docker compose logs -f app
- Restart:                     docker compose restart
- Stop everything:             docker compose down        (data is kept)
- Delete all data:             docker compose down -v     (careful)
- Backup:                      docker volume ls   (find the volume, e.g. kb-assistant_appdata)
    docker run --rm -v kb-assistant_appdata:/data -v $PWD:/backup alpine tar czf /backup/backup.tgz -C /data .

## Costs and cleanup
You pay for the instance while it runs, the disk, and the public IP address. Check the AWS pricing page for
your region. Stop the instance when you're not using it (disk and IP still cost a little); terminate the
instance and release the Elastic IP when you're done for good.

## Troubleshooting
- Site doesn't load: security group missing port 80, or the app is still starting (check the logs).
- 502 error: app crashed or still starting; docker compose logs app
- Login does nothing over a domain: COOKIE_SECURE=1 but you're on http://, or the reverse.
- "model not found": change MODEL in .env, then docker compose up -d
- Out of memory / container killed: use a bigger instance type.
