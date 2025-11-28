# Book Arbitrage Scraper

A comprehensive web application for discovering profitable book arbitrage opportunities on BookFinder.com. The system runs 24/7, automatically checking ISBNs for price discrepancies between buy and buyback offers.

## Features

### Core Functionality
- **Automated ISBN Monitoring**: Checks up to 19,000 ISBNs every 24-48 hours
- **Profit Detection**: Compares lowest buy prices (new & used) against best buyback offers
- **Email Alerts**: Automatic notifications when profitable opportunities are found
- **Smart Filtering**: Block specific sellers, countries, or websites
- **Data Export**: Export profitable finds to CSV format
- **24/7 Scheduler**: Background job scheduler runs hourly checks

### Admin Dashboard
- **Overview**: Real-time statistics and system status
- **ISBN Manager**: Upload individual or bulk ISBNs
- **Filter Manager**: Customize banned entities (sellers, countries, websites)
- **Profitable Finds**: View all discovered opportunities with detailed information
- **System Logs**: Monitor scraper activity, errors, and successes
- **Settings**: Change password and configure email notifications

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLite**: Database for ISBNs, filters, and profitable finds
- **Playwright**: Browser automation for web scraping
- **APScheduler**: Background task scheduling
- **Gmail**: Email notification service
- **JWT**: Secure authentication
- 
### Frontend
- **React**: UI framework
- **Tailwind CSS**: Styling
- **Shadcn/UI**: Component library
- **Axios**: HTTP client
- **React Router**: Navigation

⚠️ **Change the default password immediately after first login!**

### Adding ISBNs
1. Navigate to "ISBN List"
2. Add ISBNs individually or bulk upload
3. The scraper will automatically check them every 24-48 hours

### Email Notifications Setup
To enable email alerts, add to `/app/backend/.env`:
```env
SENDGRID_API_KEY=your_key_here
FROM_EMAIL=alerts@yourdomain.com
ADMIN_EMAIL=your@email.com
```
Then restart: `sudo supervisorctl restart backend`

## How It Works

1. **Scheduler runs every hour**
2. Selects ISBNs not checked in 24 hours
3. Scrapes BookFinder.com using Playwright
4. Extracts prices and applies filters
5. Calculates profit opportunities
6. Sends email alerts for profitable finds
7. Logs all activities
