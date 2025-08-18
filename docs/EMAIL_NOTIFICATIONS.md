# Email Notifications for Tmux Orchestrator

## Overview

The Tmux Orchestrator now supports email notifications when projects complete, whether run individually or as part of batch processing. This feature helps you stay informed about the status of your orchestrations without having to monitor the tmux sessions constantly.

## Features

- **Individual Project Notifications**: Get notified when a single project orchestration completes
- **Batch Processing Notifications**: Receive notifications for each project in a batch, plus a summary
- **Failure Alerts**: Immediate notification if a project fails with error details
- **Rich Email Format**: HTML and plain text emails with project details, duration, and session information
- **Configurable via .env**: Simple configuration using environment variables

## Configuration

### 1. Create .env File

Copy the example configuration file and customize it:

```bash
cp .env.example .env
```

### 2. Configure Email Settings

Edit the `.env` file with your email provider settings:

```env
# SMTP Server Settings
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true

# Email credentials
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Email addresses
SENDER_EMAIL=your-email@gmail.com
RECIPIENT_EMAIL=recipient@example.com

# Optional: Subject line prefix
EMAIL_SUBJECT_PREFIX=[DEV]
```

### 3. Email Provider Setup

#### Gmail
1. Enable 2-factor authentication on your Google account
2. Generate an app-specific password at: https://myaccount.google.com/apppasswords
3. Use the app password instead of your regular password in the .env file

#### Other Providers
- **Office 365**: `smtp.office365.com` (port 587)
- **Outlook**: `smtp-mail.outlook.com` (port 587)
- **Yahoo**: `smtp.mail.yahoo.com` (port 587 or 465)
- **Custom/Corporate**: Contact your IT department for SMTP settings

## Email Types

### 1. Project Completion Email

Sent when an individual project completes successfully:

**Subject**: ✅ Project Completed: [Project Name]

**Contents**:
- Project name and specification path
- Tmux session name for attachment
- Duration of orchestration
- Registry directory location
- Team configuration details
- Instructions to attach to the session

### 2. Project Failure Email

Sent when a project fails:

**Subject**: ❌ Project Failed: [Project Name]

**Contents**:
- Project name and specification path
- Error details and stack trace
- Timestamp of failure
- Suggestions for troubleshooting

### 3. Batch Summary Email

Sent after batch processing completes:

**Subject**: ✅/⚠️ Batch Processing Complete: X/Y Succeeded

**Contents**:
- Total projects processed
- Number of successful completions
- Number of failures
- Total processing duration
- List of completed projects
- List of failed projects (if any)

## Usage

### Individual Projects

Email notifications are automatic when running individual projects:

```bash
./auto_orchestrate.py --project /path/to/project --spec spec.md
```

Upon completion, you'll receive an email with:
- Project status (completed/failed)
- Session name to attach to
- Duration and other metadata

### Batch Processing

When using batch mode, you'll receive:
1. Individual emails for failed projects (as they fail)
2. A summary email when the batch completes or when no more projects are queued

```bash
# Queue multiple projects
./auto_orchestrate.py --spec spec1.md --spec spec2.md --spec spec3.md

# Start batch processing daemon
uv run scheduler.py --queue-daemon
```

## Monitoring and Debugging

### Check Email Configuration

The system will log whether email notifications are enabled:

```
INFO - Email notifications enabled - will send to recipient@example.com
```

Or if configuration is missing:

```
INFO - Email notifications disabled - missing configuration in .env file
```

### Email Failures

Email sending failures are logged but don't stop the orchestration:

```
DEBUG - Failed to send completion email: [error details]
```

Check `scheduler.log` for batch processing email logs.

## Security Considerations

1. **Never commit .env files**: The `.env` file contains sensitive credentials and should never be committed to version control
2. **Use app passwords**: Don't use your main email password; use app-specific passwords
3. **Secure SMTP**: Always use TLS/SSL when available (`SMTP_USE_TLS=true`)
4. **Minimal permissions**: Use a dedicated email account with minimal permissions if possible

## Troubleshooting

### Emails Not Sending

1. **Check .env file exists**: Ensure `.env` is in the same directory as `auto_orchestrate.py`
2. **Verify credentials**: Test your SMTP credentials with a simple email client
3. **Check firewall**: Ensure outbound connections to SMTP port are allowed
4. **Enable debug logging**: Set logging level to DEBUG to see detailed error messages

### Gmail Specific Issues

- **Less secure apps**: Not recommended; use app passwords instead
- **2FA required**: Gmail requires 2-factor authentication for app passwords
- **Quota limits**: Gmail has sending limits (500 emails/day for personal accounts)

### Corporate Email Issues

- **Firewall blocking**: Corporate networks may block SMTP ports
- **Authentication methods**: Some corporate servers require specific auth methods
- **Internal SMTP servers**: May need to use internal SMTP relay servers

## Advanced Configuration

### Subject Line Prefix

You can add a custom prefix to all email subjects to help with filtering and organization:

```env
# Examples of useful prefixes:
EMAIL_SUBJECT_PREFIX=[DEV]        # Development environment
EMAIL_SUBJECT_PREFIX=[PROD]       # Production environment
EMAIL_SUBJECT_PREFIX=[ClientA]    # Client-specific projects
EMAIL_SUBJECT_PREFIX=[TeamBlue]   # Team-specific notifications
EMAIL_SUBJECT_PREFIX=[AWS]        # Cloud provider specific
```

This prefix will be automatically added to all email subjects:
- Without prefix: `✅ Project Completed: MyProject`
- With `[DEV]` prefix: `[DEV] ✅ Project Completed: MyProject`

This is particularly useful for:
- **Email filtering**: Create rules based on the prefix
- **Environment separation**: Distinguish dev/staging/prod notifications
- **Multi-tenant systems**: Separate notifications by client
- **Team organization**: Route emails to appropriate team members

### Custom Email Templates

To customize email templates, modify the `email_notifier.py` file:

- `send_project_completion_email()`: Individual project emails
- `send_batch_summary_email()`: Batch summary emails

### Disable Notifications

To temporarily disable notifications without removing configuration:

```bash
# Remove or rename .env file
mv .env .env.disabled
```

Or set an environment variable:

```bash
export DISABLE_EMAIL_NOTIFICATIONS=true
./auto_orchestrate.py --project /path --spec spec.md
```

## Best Practices

1. **Test configuration first**: Send a test email before running important orchestrations
2. **Monitor spam folder**: Automated emails might be marked as spam initially
3. **Use descriptive project names**: Makes email subjects more meaningful
4. **Archive important notifications**: Save emails for failed projects for debugging
5. **Set up email filters**: Create rules to organize orchestration emails

## Future Enhancements

Potential future improvements:

- Slack/Discord webhook integration
- SMS notifications for critical failures
- Configurable email templates
- Progress updates during long orchestrations
- Daily/weekly summary reports
- Integration with monitoring dashboards