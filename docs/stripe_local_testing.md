# Testing Stripe Integration Locally

This guide explains how to test Stripe integration in your local development environment using ngrok
for webhook testing.

## Prerequisites

1. A Stripe account (you can sign up at [stripe.com](https://stripe.com))
1. ngrok installed on your machine
1. Your local development environment running on `127.0.0.1:5000` with HTTPS

## Setting Up ngrok

1. **Install ngrok**

   ```bash
   # Using Homebrew (macOS)
   brew install ngrok

   # Using npm
   npm install ngrok -g

   # Or download directly from ngrok.com
   ```

1. **Sign up and connect your ngrok account**

   - Go to [ngrok.com](https://ngrok.com) and create an account

   - Get your auth token from the dashboard

   - Configure ngrok with your auth token:

     ```bash
     ngrok config add-authtoken YOUR_AUTH_TOKEN
     ```

1. **Start ngrok**

   ```bash
   # For HTTPS local development
   ngrok http https://127.0.0.1:5000 --host-header=127.0.0.1
   ```

1. **Note your ngrok URL**

   - After starting ngrok, you'll see a URL like: `https://xxxx-xx-xx-xxx-xx.ngrok-free.app`
   - Keep this terminal window open to maintain the tunnel

## Configuring Stripe Webhooks

1. **Log into your Stripe Dashboard**

   - Go to [Stripe Dashboard](https://dashboard.stripe.com)
   - Navigate to "Developers" → "Webhooks"

1. **Add Endpoint**

   - Click "Add endpoint"

   - Enter your ngrok URL + webhook path:

     ```text
     https://xxxx-xx-xx-xxx-xx.ngrok-free.app/api/v1/stripe/webhook
     ```

1. **Select Events** Subscribe to the following checkout events:

   - `checkout.session.completed`
   - `checkout.session.expired`
   - `checkout.session.async_payment_succeeded`
   - `checkout.session.async_payment_failed`

   Also subscribe to the following subscription events:

   - `customer.subscription.updated` (for handling subscription cancellations)
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

1. **Get Webhook Secret**

   - After creating the webhook, you'll see a "Signing secret" key

   - Copy this key and update your `.env` file:

     ```text
     STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
     ```

## Testing the Integration

1. **Start your local development server**

   ```bash
   flask run --debug --cert ./cert.pem --key key.pem
   ```

1. **Start ngrok** (if not already running)

   ```bash
   ngrok http https://127.0.0.1:5000 --host-header=127.0.0.1
   ```

1. **Test Subscription Flow**

   - Go to your profile page through the ngrok URL:

     ```text
     https://xxxx-xx-xx-xxx-xx.ngrok-free.app/profile
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
     - The webhook is received (check logs and ngrok interface)
     - Your application correctly downgrades you to the Free plan

1. **Monitor Webhook Events**

   - Watch the Stripe Dashboard's webhook section
   - Check your application logs
   - Use ngrok's web interface (available at [http://localhost:4040](http://localhost:4040)) to
     inspect webhook deliveries

## Troubleshooting

### Common Issues

1. **Webhook Not Received**

   - Verify ngrok is running
   - Check webhook URL in Stripe Dashboard
   - Ensure webhook secret is correctly set in `.env`

1. **SSL Certificate Issues**

   - Ensure you're using HTTPS with ngrok
   - Check your local SSL certificates are valid

1. **Payment Flow Issues**

   - Verify Stripe API keys are correct
   - Check browser console for JavaScript errors
   - Ensure your test mode is active in Stripe Dashboard

### Stripe Test Cards

| Card Number | Description | |----------------------|---------------------| | 4242 4242 4242 4242 |
Success | | 4000 0000 0000 0002 | Declined | | 4000 0000 0000 9995 | Insufficient funds | | 4000
0000 0000 3220 | 3D Secure required |

## Best Practices

1. **Always use test API keys** in development
1. **Monitor webhook delivery** in Stripe Dashboard
1. **Check application logs** for detailed error messages
1. **Use different browsers** for testing multiple accounts
1. **Clear browser cache** if experiencing persistent issues

## Additional Resources

- [Stripe Testing Documentation](https://stripe.com/docs/testing)
- [ngrok Documentation](https://ngrok.com/docs)
- [Stripe Webhook Guide](https://stripe.com/docs/webhooks)
- [Test Clock for Subscriptions](https://stripe.com/docs/billing/testing/test-clocks)
