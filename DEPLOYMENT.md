# 🚀 Xpanse.ai — EC2 Deployment Guide (Simplest Path)

Deploy Xpanse.ai on a single EC2 instance in under 30 minutes. No containers, no load balancers, no ECS — just a VM running your Streamlit app.

---

## Prerequisites

Before you start, ensure you have:

- [ ] An AWS account with console access
- [ ] Your `.env` values ready (TAVILY_API_KEY, ARCHIVE_KB_ID, BRAND_KB_ID)
- [ ] AWS credentials configured locally (for launching the instance via CLI) — or just use the AWS Console
- [ ] Your project code pushed to a Git repository (GitHub, CodeCommit, etc.)

---

## Step 1: Launch an EC2 Instance

### Via AWS Console:

1. Go to **EC2 → Launch Instance**
2. Configure:

| Setting | Value |
|---------|-------|
| Name | `xpanse-ai` |
| AMI | **Amazon Linux 2023** (or Ubuntu 24.04) |
| Instance type | **t3.small** (2 vCPU, 2 GB RAM — sufficient for Streamlit + LangGraph) |
| Key pair | Create or select an existing key pair (you'll need this to SSH in) |
| Network | Default VPC, public subnet, **Auto-assign public IP: Enable** |
| Security Group | Create new — see Step 2 |
| Storage | 20 GB gp3 (default is fine) |

3. Under **Advanced Details → IAM instance profile**: attach a role with Bedrock permissions (see Step 3)
4. Click **Launch Instance**

---

## Step 2: Configure Security Group

Create a security group with these inbound rules:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your IP (`x.x.x.x/32`) | SSH access for setup |
| Custom TCP | 8501 | `0.0.0.0/0` (or your IP for restricted access) | Streamlit UI |

> ⚠️ For production, restrict port 8501 to your team's IP range or VPN CIDR instead of `0.0.0.0/0`.

---

## Step 3: Create an IAM Role for the EC2 Instance

This lets the app call Bedrock without hardcoding AWS credentials.

1. Go to **IAM → Roles → Create Role**
2. Trusted entity: **AWS Service → EC2**
3. Attach a policy with this JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:Converse"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0"
    },
    {
      "Sid": "BedrockKBRetrieve",
      "Effect": "Allow",
      "Action": [
        "bedrock:Retrieve"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1:*:knowledge-base/LDM48BQ6MA",
        "arn:aws:bedrock:us-east-1:*:knowledge-base/MCTXWGB1FF"
      ]
    }
  ]
}
```

4. Name it `xpanse-ai-ec2-role`
5. Attach it to your EC2 instance (Actions → Security → Modify IAM Role)

---

## Step 4: SSH into the Instance

```bash
ssh -i your-key.pem ec2-user@<PUBLIC_IP>
```

For Ubuntu AMI, use `ubuntu@<PUBLIC_IP>` instead.

---

## Step 5: Install Python 3.14 and uv

### Amazon Linux 2023:

```bash
# Install build dependencies
sudo dnf install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel make

# Download and install Python 3.14
cd /tmp
wget https://www.python.org/ftp/python/3.14.0/Python-3.14.0.tgz
tar xzf Python-3.14.0.tgz
cd Python-3.14.0
./configure --enable-optimizations
sudo make altinstall

# Verify
python3.14 --version

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### Ubuntu 24.04 (alternative):

```bash
sudo apt update && sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install -y python3.14 python3.14-venv python3.14-dev

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

---

## Step 6: Clone and Install the Project

```bash
cd ~
git clone <YOUR_REPO_URL> xpanse-ai
cd xpanse-ai

# Create venv and install dependencies
uv sync
```

---

## Step 7: Configure Environment Variables

```bash
cat > .env << 'EOF'
TAVILY_API_KEY=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
ARCHIVE_KB_ID=LDM48BQ6MA
BRAND_KB_ID=MCTXWGB1FF
AWS_REGION=us-east-1
EOF
```

> Replace with your actual keys. The IAM role handles AWS auth — no access keys needed.

---

## Step 8: Test the App

```bash
cd ~/xpanse-ai
uv run streamlit run src/ui.py --server.port 8501 --server.address 0.0.0.0
```

Open your browser: `http://<PUBLIC_IP>:8501`

Verify:
- [ ] UI loads with both modes visible
- [ ] System health LEDs show green for Archive KB, Brand KB, Tavily, Bedrock
- [ ] Launch a test campaign and confirm agents execute

Press `Ctrl+C` to stop once verified.

---

## Step 9: Run as a Background Service (Persistent)

Create a systemd service so the app survives SSH disconnects and auto-starts on reboot:

```bash
sudo tee /etc/systemd/system/xpanse.service << 'EOF'
[Unit]
Description=Xpanse.ai Streamlit App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/xpanse-ai
Environment="PATH=/home/ec2-user/.local/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/ec2-user/.local/bin/uv run streamlit run src/ui.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable xpanse
sudo systemctl start xpanse

# Check status
sudo systemctl status xpanse

# View logs
sudo journalctl -u xpanse -f
```

---

## Step 10: (Optional) Add HTTPS with Caddy

If you want HTTPS without dealing with ALB/ACM certificates:

```bash
# Install Caddy
sudo dnf install -y 'dnf-command(copr)'
sudo dnf copr enable @caddy/caddy -y
sudo dnf install -y caddy

# Configure reverse proxy
sudo tee /etc/caddy/Caddyfile << 'EOF'
xpanse.yourdomain.com {
    reverse_proxy localhost:8501
    reverse_proxy /stream/* localhost:8501
}
EOF

# Start Caddy
sudo systemctl enable caddy
sudo systemctl start caddy
```

Point your domain's DNS A record to the EC2 public IP. Caddy auto-provisions Let's Encrypt certificates.

---

## Maintenance Commands

```bash
# Update code
cd ~/xpanse-ai
git pull
uv sync
sudo systemctl restart xpanse

# View live logs
sudo journalctl -u xpanse -f

# Stop the app
sudo systemctl stop xpanse

# Check if running
sudo systemctl status xpanse
```

---

## Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| EC2 t3.small (on-demand) | ~$15 |
| EBS 20GB gp3 | ~$2 |
| Bedrock Nova Pro (pay-per-token) | ~$5-50 (usage dependent) |
| Bedrock KB retrieval | ~$2-10 |
| Tavily API | Free tier or ~$20 |
| **Total** | **~$25-100/mo** |

> 💡 Use a **Reserved Instance** or **Savings Plan** to cut EC2 cost by ~40% if running long-term.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Run `uv sync` again |
| Bedrock `AccessDeniedException` | Check IAM role is attached and has correct permissions |
| KB retrieval returns empty | Verify KB IDs in `.env` match your Bedrock console |
| Port 8501 not reachable | Check security group inbound rules |
| App crashes on reboot | Verify systemd service is enabled: `sudo systemctl is-enabled xpanse` |
| Streamlit WebSocket errors | Ensure security group allows the full TCP connection (not just HTTP) |

---

## Security Checklist

- [ ] Restrict port 8501 to known IPs (not `0.0.0.0/0`) for internal tools
- [ ] Never commit `.env` to Git
- [ ] Use IAM role (not hardcoded keys) for AWS access
- [ ] Enable CloudWatch agent for monitoring (optional)
- [ ] Set up a budget alert in AWS Billing to avoid surprise Bedrock costs
- [ ] Consider adding Cognito or basic auth if exposed to the internet
