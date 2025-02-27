# Testing Stripe Integration Locally

This guide explains how to test Stripe integration in your local development environment using the
Stripe CLI for webhook testing.

## Prerequisites

1. A Stripe account (you can sign up at [stripe.com](https://stripe.com))
1. Your local development environment running on `127.0.0.1:5000` with HTTPS
1. Stripe CLI installed on your machine

## Obtaining Stripe API Keys

Before setting up the Stripe CLI, you need to obtain your API keys from the Stripe Dashboard:

1. **Log into your Stripe Dashboard**

   - Go to [Stripe Dashboard](https://dashboard.stripe.com)

1. **Navigate to Developers > API keys**

   - Direct link: [https://dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys)

1. **View your API keys**

   - You'll see two types of keys:
     - **Publishable key**: Starts with `pk_test_` (for test mode) or `pk_live_` (for live mode)
     - **Secret key**: Starts with `sk_test_` (for test mode) or `sk_live_` (for live mode)

   ![Stripe API Keys](https://stripe.com/img/documentation/keys.png)

1. **Copy your API keys**

   - For development, use the **test mode** keys
   - Click "Reveal test key" to see your secret key
   - Copy both keys and add them to your `.env` file:

   ```text
   STRIPE_PUBLISHABLE_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   ```

   > ⚠️ **Important**: Never commit your secret key to version control or share it publicly. Always
   > use environment variables to store sensitive keys.

1. **Toggle between test and live mode**

   - Use the toggle in the dashboard to switch between test and live mode
   - For development and testing, always use test mode keys

## Setting Up Stripe CLI

1. **Install the Stripe CLI**

   ```bash
   # Using Homebrew (macOS)
   brew install stripe/stripe-cli/stripe

   # For other platforms, download from:
   # https://stripe.com/docs/stripe-cli
   ```

1. **Log in with your Stripe account**

   ```bash
   stripe login
   ```

   This will open your browser and prompt you to authorize the CLI to access your Stripe account.
   After authorization, the CLI will receive a webhook signing secret.

1. **Forward events to your local server**

   ```bash
   # For HTTPS with self-signed certificates (skip verification)
   stripe listen --forward-to https://localhost:5000/api/v1/stripe/webhook --skip-verify
   ```

   > Note: Use `--skip-verify` when working with self-signed certificates in local development to
   > bypass SSL certificate verification.

   The CLI will display a webhook signing secret. Copy this and update your `.env` file:

   ```text
   STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
   ```

1. **Start Lorelai**

Now that you have all the `STRIPE_` environment variables set, start Lorelai locally using your
preferred method.

1. **Trigger test events**

   In a new terminal window, you can trigger specific events to test your webhook handlers:

   ```bash
   # Test a successful payment
   stripe trigger payment_intent.succeeded

   # Test a successful subscription
   stripe trigger customer.subscription.created

   # Test a successful checkout session
   stripe trigger checkout.session.completed
   ```

   The Stripe CLI supports triggering many different event types. You can see the full list with:

   ```bash
   stripe trigger --help
   ```

1. **Test Subscription Flow**

   - Go to your profile page:

     ```text
     https://localhost:5000/profile
     ```

   - Try subscribing to a plan

   - Use Stripe test card numbers:

     - Success: `4242 4242 4242 4242`
     - Failure: `4000 0000 0000 0002`

1. **Test Billing Portal and Cancellation**

   - After subscribing to a paid plan, a "Manage Billing" button will appear on your profile page

   - Click this button to be redirected to the Stripe Customer Portal

   - In the portal, you can:

     - Cancel your subscription
     - Update payment methods
     - View invoices

   - Test canceling your subscription and confirm that:

     - Your subscription status updates in Stripe
     - The webhook is received (check CLI output and application logs)
     - Your application correctly downgrades you to the Free plan

1. **Monitor Webhook Events**

   - The CLI will display incoming webhook events in real-time in the terminal window where
     `stripe listen` is running

   - You can also check your application logs to verify the events are being processed correctly

   - Use the `--events` flag to filter specific event types:

     ```bash
     stripe listen --events checkout.session.completed,customer.subscription.updated --forward-to
     localhost:5000/api/v1/stripe/webhook --skip-verify
     ```

## Troubleshooting

### Common Issues

1. **Webhook Not Received**

   - Check that the `stripe listen` command is running
   - Verify the forwarding URL matches your application's webhook endpoint
   - Ensure webhook secret is correctly set in `.env`

1. **SSL Certificate Issues**

   - Check your local SSL certificates are valid

   - The Stripe CLI handles the secure connection between Stripe and your local server

   - If using self-signed certificates, use the `--skip-verify` flag:

     ```bash
     stripe listen --forward-to https://localhost:5000/api/v1/stripe/webhook --skip-verify
     ```

   - If you see errors like `"localhost" certificate is not trusted`, this indicates a certificate
     verification issue that can be resolved with the solutions above

1. **Payment Flow Issues**

   - Verify Stripe API keys are correct
   - Check browser console for JavaScript errors
   - Ensure your test mode is active in Stripe Dashboard
   - Verify you're triggering the correct event types

1. **API Key Issues**

   - Ensure you're using the correct API keys (test vs. live)
   - Check that both STRIPE_PUBLISHABLE_KEY and STRIPE_SECRET_KEY are set in your `.env` file
   - Verify that your application is correctly loading the environment variables
   - If using Flask, ensure you're using `os.environ.get('STRIPE_SECRET_KEY')` to access the keys

1. **Stripe CLI Issues**

   - If the CLI can't connect, try logging in again with `stripe login`
   - Ensure you have the latest version with `stripe version`
   - Check your network connection and firewall settings

### Stripe Test Cards

| Card Number | Description | |---------------------|---------------------| | 4242 4242 4242 4242 |
Success | | 4000 0000 0000 0002 | Declined | | 4000 0000 0000 9995 | Insufficient funds | | 4000
0000 0000 3220 | 3D Secure required |

## Best Practices

1. **Always use test API keys** in development
1. **Monitor webhook delivery** in CLI output
1. **Check application logs** for detailed error messages
1. **Use different browsers** for testing multiple accounts
1. **Clear browser cache** if experiencing persistent issues
1. **Save common CLI commands** in a project-specific script or documentation for easy reference
1. **Use event filtering** to focus on specific events during testing
1. **Secure your API keys**:
   - Never hardcode API keys in your application code
   - Use environment variables for all sensitive keys
   - Include only placeholder values in `.env.example` files
   - Add `.env` to your `.gitignore` file
1. **Rotate API keys** if you suspect they've been compromised

## Additional Resources

- [Stripe Testing Documentation](https://stripe.com/docs/testing)
- [Stripe CLI Documentation](https://stripe.com/docs/stripe-cli)
- [Stripe Webhook Guide](https://stripe.com/docs/webhooks)
- [Stripe API Reference](https://stripe.com/docs/api)
- [Test Clock for Subscriptions](https://stripe.com/docs/billing/testing/test-clocks)
- [SSL Certificate Troubleshooting](https://stripe.com/docs/webhooks/test#use-the-cli-to-test-webhooks)
