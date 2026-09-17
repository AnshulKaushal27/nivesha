# Deploying Nivesha on the AWS Free plan

One small EC2 instance runs everything: Postgres, the API with its scheduler,
the Next.js frontend, and Caddy for HTTPS with a single login. No RDS, no load
balancer, no NAT gateway. Expected burn on the credit-based Free plan:
about **$14/month** (instance ≈ $8.5, 30 GB disk ≈ $2.4, public IPv4 ≈ $3.6),
so your $100 covers the whole 173-day window with room to spare. An ARM
`t4g.micro` is about 25 % cheaper and works identically.

Everything below that says *you* is a console click I cannot make for you.
Everything else is scripted in `infra/`.

---

## 0. Before creating anything: stop surprise bills (5 min, you)

1. **Billing → Budgets → Create budget → Zero spend budget**, with your email. Then a second one at **$50**.
2. **Billing → Billing preferences → enable "Receive CloudWatch billing alerts"**.
3. Know the traps, all avoided by this setup: NAT Gateway, Elastic Load Balancer, Route 53 hosted zone, RDS, `t3` *unlimited* credit mode, unattached Elastic IPs, CloudWatch log ingestion.

## 1. A free hostname (3 min, you)

Let's Encrypt needs a domain. [DuckDNS](https://www.duckdns.org) is free:
sign in, create a subdomain such as `nivesha` → `nivesha.duckdns.org`, and copy
your **token**. The instance keeps the record pointed at itself every 5 minutes,
so you do not need an Elastic IP.

## 2. Launch the instance (5 min, you)

EC2 → Launch instance:

| Setting | Value |
| --- | --- |
| Name | nivesha |
| AMI | **Ubuntu Server 24.04 LTS** (x86 for t3.micro, arm64 for t4g.micro) |
| Instance type | `t3.micro` (or `t4g.micro`) |
| Key pair | create one, download the `.pem` |
| Network → security group | allow **SSH 22 from My IP**, **HTTP 80** and **HTTPS 443** from anywhere |
| Storage | **30 GiB gp3** (the free-plan maximum) |
| Advanced → Credit specification | **Standard** (never *Unlimited*) |

Launch. Note the **Public IPv4 address**. In DuckDNS, set your subdomain's IP
to it once (the updater takes over afterwards).

## 3. Deploy from this laptop (10–15 min, mostly waiting)

Prerequisites on the Mac: `brew install libpq` (for `pg_dump`), and
`chmod 400 ~/Downloads/nivesha.pem`.

```bash
cd ~/Desktop/AI-Investment-Arena
export HOST=ubuntu@<public-ip>
alias sshn="ssh -i ~/Downloads/nivesha.pem"

# let the deploy script use your key
export GIT_SSH_COMMAND="ssh -i ~/Downloads/nivesha.pem"; export RSYNC_RSH="ssh -i ~/Downloads/nivesha.pem"

FIRST=1 DOMAIN=nivesha.duckdns.org DUCKDNS_TOKEN=<token> AUTH_USER=anshul AUTH_PASS='<strong password>' \
  infra/deploy.sh $HOST --with-data
```

What that does: syncs the source (including your `backend/.env` with its keys),
dumps your local Postgres (all bars, scores, predictions, arena history) and
restores it on the server, then runs `infra/ec2/bootstrap.sh`, which installs
everything, builds the frontend, writes the systemd units and the Caddyfile,
requests the certificate, and starts the services.

Open **https://nivesha.duckdns.org**, log in with `AUTH_USER` / `AUTH_PASS`.
The System page should read *Everything is running* within a minute.

## 4. What is different in production

- `backend/.env` on the server gets `DATABASE_URL` for the local Postgres,
  `CORS_ORIGINS=https://<your domain>` and `PREDICTOR_MAX_YEARS=8`. The last one
  matters: training on all 20 years needs about 3 GB of RAM and would be killed
  on a 1 GB box; 8 years fits with the 4 GB swap the script creates. The
  walk-forward metrics on the page will reflect the shorter window.
- The API listens on `127.0.0.1:8000` only; the world reaches it through Caddy
  at `https://<domain>/api/...`. The frontend is built with that URL.
- The scheduler runs inside the API service, so all the jobs (08:40 round,
  15:45 close, 20:15 nightly, health checks) start on boot and restart on
  failure. `systemctl status nivesha-api` shows it.
- Nightly `pg_dump` to `/opt/nivesha/backups` (14 kept). Add
  `BACKUP_S3_BUCKET=<bucket>` to `backend/.env` and install the AWS CLI on the
  instance to copy them to S3 (5 GB is within the always-free allowance).
- Alerts: put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `backend/.env`
  before deploying, or add them later and `sudo systemctl restart nivesha-api`.

## 5. Day-to-day

```bash
infra/deploy.sh $HOST                    # push code changes: sync, migrate, rebuild, restart
sshn $HOST 'sudo journalctl -u nivesha-api -f'          # live backend log
sshn $HOST 'sudo journalctl -u nivesha-web -n 100'      # frontend log
sshn $HOST 'sudo systemctl restart nivesha-api'
sshn $HOST 'sudo -u nivesha /usr/local/bin/nivesha-backup'   # backup now
```

Upstox: your extended token is valid until 22 May 2027; the 07:45 check will
warn two weeks before. Update `UPSTOX_ANALYTICS_TOKEN` in the server's
`backend/.env` and restart the API when you renew it.

## 6. If something is off

| Symptom | Look at |
| --- | --- |
| Site does not load / certificate error | `sudo journalctl -u caddy -n 50`; DNS must point at the instance and ports 80/443 must be open |
| Login loop | the password is bcrypt-hashed in `/etc/caddy/Caddyfile`; re-run bootstrap with a new `AUTH_PASS` |
| API 502 | `sudo systemctl status nivesha-api`; usually a bad `.env` value or a migration that needs `alembic upgrade head` |
| Out of memory during training | `PREDICTOR_MAX_YEARS` lower (6), or move training off the box |
| Nothing new after a trading day | System page → Open alerts; the 21:30 freshness check names the failed job |

## 7. Costs to watch on the Free plan

Billing → Free Tier shows credit usage. At ≈ $14/month you have ~7 months of
runway on $100; the plan expires around **9 March 2027** regardless, when the
account must move to paid or the instance to another host. Everything in this
setup is portable: any Ubuntu VM with the same script works.
