# Cloudflare Tunnel Setup

## Steps to configure your tunnel:

1. **Create tunnel in Cloudflare dashboard**:
   ```bash
   cloudflared tunnel create calendar-builder
   ```

2. **Copy tunnel credentials**:
   - Download the .json credentials file
   - Place it in this directory as `<tunnel-id>.json`

3. **Update configuration**:
   - Edit `config.yml` and replace `your-tunnel-id-here` with your actual tunnel ID
   - Verify domain name is correct: `calendar.flyhomemnlab.com`

4. **Configure DNS**:
   - In Cloudflare dashboard, add CNAME record:
   - Name: `calendar`
   - Target: `<tunnel-id>.cfargotunnel.com`

5. **Add tunnel token to .env**:
   ```
   CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token-here
   ```

6. **Test the tunnel**:
   ```bash
   docker-compose up cloudflared
   ```

## Security Notes:
- Keep the .json credentials file secure and never commit it to git
- The tunnel provides secure access without opening firewall ports
- SSL/TLS termination is handled by Cloudflare
