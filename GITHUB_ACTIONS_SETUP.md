# GitHub Actions CI/CD Setup for Social Studio

This project uses GitHub Actions for automated deployment to your Azure VM.

## What Happens on Push

When you push to `main` or `dev` branches:
1. ✅ Checks out code
2. ✅ Runs Python syntax checks
3. ✅ Builds Docker images (API & Worker)
4. ✅ Transfers images to VM
5. ✅ Deploys using `deploy-to-vm.sh`
6. ✅ Runs health check
7. ✅ Cleans up artifacts

## Required GitHub Secrets

You need to add these secrets to your GitHub repository:

### 1. SSH_PRIVATE_KEY

This is the content of your SSH private key file.

**Get the key content:**
```bash
cat ~/Downloads/social-studio-vm-key.pem
```

**Add to GitHub:**
1. Go to your repository on GitHub
2. Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `SSH_PRIVATE_KEY`
5. Value: Paste the entire content of the PEM file (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`)

### 2. KNOWN_HOSTS

This is the SSH fingerprint of your VM.

**Get the known hosts entry:**
```bash
ssh-keyscan -H 130.131.236.20
```

**Add to GitHub:**
1. Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `KNOWN_HOSTS`
4. Value: Paste the output from ssh-keyscan command

Example output:
```
|1|abcd1234...= ssh-rsa AAAAB3NzaC1yc2EAAAA...
```

## Setup Instructions

### Step 1: Add GitHub Secrets

```bash
# On your local machine

# 1. Get SSH private key
echo "Copy this content for SSH_PRIVATE_KEY secret:"
cat ~/Downloads/social-studio-vm-key.pem

# 2. Get known hosts
echo "Copy this content for KNOWN_HOSTS secret:"
ssh-keyscan -H 130.131.236.20
```

### Step 2: Add Secrets to GitHub

1. Go to https://github.com/Ai-firelab/SocialStudio
2. Settings → Secrets and variables → Actions
3. Add both secrets as described above

### Step 3: Test the Workflow

Make a small change and push to dev:

```bash
git checkout dev

# Make a small change (example)
echo "# Test deployment" >> README.md

git add .
git commit -m "Test CI/CD deployment"
git push origin dev
```

### Step 4: Monitor Deployment

1. Go to https://github.com/Ai-firelab/SocialStudio/actions
2. You'll see the workflow running
3. Click on the workflow to see detailed logs
4. Build typically takes 5-7 minutes

## Workflow File Location

The workflow is defined in: `.github/workflows/azure-deploy.yml`

## Environment Variables (in workflow)

```yaml
VM_HOST: '130.131.236.20'
VM_USER: 'azureuser'
PYTHON_VERSION: '3.10'
```

These are already configured in the workflow file.

## Troubleshooting

### Issue: Permission denied (publickey)

**Solution:** Make sure `SSH_PRIVATE_KEY` secret contains the complete PEM file content, including the header and footer lines.

### Issue: Host key verification failed

**Solution:** Make sure `KNOWN_HOSTS` secret is set correctly. Run `ssh-keyscan -H 130.131.236.20` again and update the secret.

### Issue: scp: command not found

**Solution:** This shouldn't happen on GitHub Actions runners, but if it does, the workflow will fail. Check the Actions logs.

### Issue: Docker build fails

**Solution:**
- Check if `requirements.txt` is valid
- Check if `Dockerfile` has syntax errors
- Review the build logs in GitHub Actions

### Issue: Deployment script fails

**Solution:**
- Check the VM logs: `ssh -i ~/Downloads/social-studio-vm-key.pem azureuser@130.131.236.20 "sudo docker logs socialstudio-api"`
- Verify `.env` file exists on VM
- Check VM disk space: `df -h`

## Manual Deployment

If GitHub Actions is down or you need to deploy manually:

```bash
# On your local machine
cd /Users/mohammedek/StudioProjects/SocialStudio

# Build images
docker build -t socialstudio-api:latest .
docker build -t socialstudio-worker:latest .

# Save images
docker save socialstudio-api:latest | gzip > socialstudio-api.tar.gz
docker save socialstudio-worker:latest | gzip > socialstudio-worker.tar.gz

# Transfer to VM
scp -i ~/Downloads/social-studio-vm-key.pem socialstudio-*.tar.gz azureuser@130.131.236.20:~/
scp -i ~/Downloads/social-studio-vm-key.pem deploy-to-vm.sh azureuser@130.131.236.20:~/

# Deploy
ssh -i ~/Downloads/social-studio-vm-key.pem azureuser@130.131.236.20 'bash ~/deploy-to-vm.sh'

# Cleanup
rm socialstudio-*.tar.gz
```

## Workflow Status Badge

Add this to your README.md to show build status:

```markdown
![Deploy to Azure VM](https://github.com/Ai-firelab/SocialStudio/workflows/Deploy%20to%20Azure%20VM/badge.svg)
```

## Differences from Azure Pipelines

If you also have Azure Pipelines configured:

| Feature | GitHub Actions | Azure Pipelines |
|---------|---------------|-----------------|
| Trigger | Push to main/dev | Push to main/dev |
| Build location | GitHub runners | Azure runners |
| Deployment | Automatic | Requires environment approval |
| Cost | Free for public repos | Charges may apply |
| Configuration | `.github/workflows/` | `azure-pipelines.yml` |

You can use both or disable one:
- **To disable GitHub Actions**: Delete `.github/workflows/azure-deploy.yml`
- **To disable Azure Pipelines**: Don't set it up in Azure DevOps

## Current Deployment

After you add the secrets, the next push to `dev` will automatically:

1. Build fresh Docker images
2. Transfer them to 130.131.236.20
3. Deploy using the deployment script
4. Verify at https://social-studio.aifirelab.com/health

## Monitoring

**Check workflow runs:**
```
https://github.com/Ai-firelab/SocialStudio/actions
```

**Check deployment on VM:**
```bash
ssh -i ~/Downloads/social-studio-vm-key.pem azureuser@130.131.236.20 \
  "sudo docker ps | grep socialstudio"
```

**Check application health:**
```bash
curl https://social-studio.aifirelab.com/health
```

## Security Notes

- ✅ SSH private key is stored as a GitHub Secret (encrypted)
- ✅ Secrets are never exposed in logs
- ✅ VM is accessed via SSH key only (no passwords)
- ✅ HTTPS is enforced via nginx
- ✅ Deployment script has health checks

## Next Steps

1. **Add the two GitHub Secrets** as described above
2. **Push a change to dev** to test the deployment
3. **Monitor the workflow** in GitHub Actions tab
4. **Verify deployment** at https://social-studio.aifirelab.com

---

**Updated**: January 9, 2026
**Version**: 1.0
