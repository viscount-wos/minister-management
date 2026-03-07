# Ministry Management System - User Guide

## Overview

This application streamlines the process of assigning ministry positions during State vs State (SVS) events in Whiteout Survival based on player resources and time preferences.

## For Players

### Submitting Your Application

1. **Navigate to the home page**
2. **Click "Submit New Application"**
3. **Step 1: Enter Your Information**
   - Player ID/FID (required - this is your unique identifier, you'll need it to update later)
   - Click **"Load from WOS"** to auto-fill your game name, avatar, and furnace level from the WOS API
   - Game Name (required - auto-filled if you use Load from WOS, but editable)
   - Alliance Tag (optional, 3 characters max - displayed as `[TAG]` next to your name)
   - All your speedups in days
   - Your fire crystals, refined fire crystals, and shards

4. **Step 2: Select Time Preferences**
   - Select all times (UTC) when you're available
   - You can select multiple time slots
   - Click any time to select/deselect

5. **Step 3: Review and Confirm**
   - Double-check all information (including your avatar preview and alliance tag)
   - Click "Submit" when ready

6. **Success!**
   - Your application has been submitted
   - Remember your Player ID (FID) - you'll need it to update your submission later

### Updating Your Submission

1. **Click "Update Your Submission" from home page**
2. **Enter your Player ID (FID)**
3. **Click "Load My Data"**
4. **Edit your information**
5. **Click "Update" to save changes**

## For Ministers/Admins

### Logging In

1. **Click "Minister Administration" from home page**
2. **Enter your password**
   - Admin password: Full access
   - Minister password: Full access (same permissions)
3. **Click "Login"**

### Managing Players

1. **Go to "Players" tab**
2. **View all submissions** in a sortable table
   - Click column headers to sort
   - Use search box to find specific players (searches name, FID, and alliance tag)
   - View calculated points for each day
   - Player avatars and alliance tags `[TAG]` are displayed next to names

3. **Edit a Player**
   - Click the edit icon (pencil)
   - Modify any information (including alliance tag)
   - Click "Save"

4. **Delete a Player**
   - Click the delete icon (trash)
   - Confirm deletion

5. **Remove All Players**
   - Click "Remove All" to clear all player data
   - Requires confirmation (must type "DELETE" to confirm)

### Managing Assignments

1. **Go to "Assignments" tab**
2. **Select Day:**
   - Monday (Construction)
   - Tuesday (Research)
   - Thursday (Troop Training)

3. **Auto-Assign Players:**
   - Click "Auto Assign" button
   - System will automatically assign players based on:
     - Their point calculations
     - Their time preferences
     - Highest points get priority
   - Player cards show avatar, furnace level icon, alliance tag, and points

4. **Manual Adjustments:**
   - Drag and drop players between time slots
   - Drag players to "Unassigned" area to remove them
   - Drag unassigned players to time slots to assign them

5. **Export to Excel:**
   - Click "Export to Excel" button
   - Downloads a multi-tab workbook with:
     - **Monday** tab - Construction day assignments
     - **Tuesday** tab - Research day assignments
     - **Thursday** tab - Troop training day assignments
     - **Unassigned** tab - Players not assigned to any day
   - Each tab includes: Time Slot, FID, Alliance, Game Name, all resource columns, and Points

## Point Calculation System

### Monday - Construction Day
- **1 point** per minute of construction speedups
- **1 point** per minute of general speedups
- **30,000 points** per refined fire crystal
- **2,000 points** per fire crystal

### Tuesday - Research Day
- **1 point** per minute of research speedups
- **1 point** per minute of general speedups
- **1,000 points** per fire crystal shard

### Thursday - Troop Training Day
- **1 point** per day of troop training speedups

## Time Slots

- All times are in **UTC timezone**
- Player submission: 1-hour increments (00:00 to 23:00)
- Assignment slots: 30-minute increments (00:00, 00:30, 01:00, etc.)
- Each 1-hour player preference covers two 30-minute slots

## Tips

### For Players
- **Be honest** about your resources
- **Select multiple time slots** to increase chances of assignment
- **Update regularly** if your resources change
- **Note your FID** so you can update later

### For Ministers
- **Run auto-assign first** to get the optimal initial assignment
- **Make manual adjustments** as needed for special circumstances
- **Export to Excel** before finalizing for record-keeping
- **Check unassigned players** and try to accommodate them manually

## Troubleshooting

### Can't Find My Submission
- Make sure you're using the correct Player ID (FID)
- Check that you submitted successfully (you should have seen a success message)
- Contact your minister if the issue persists

### Wrong Information Submitted
- Use "Update Your Submission" feature
- Enter your FID and update the information

### Not Getting Assigned
- Check if you selected enough time slots
- Consider increasing your resources
- Speak with your minister about manual assignment

### Assignment Not Showing Up
- Ensure you submitted your application before the deadline
- Check your point calculation - you may need more resources
- Contact your minister for manual assignment

## Language Support

The application supports:
- 🇬🇧 English
- 🇰🇷 Korean (한국어)
- 🇨🇳 Chinese (中文)
- 🇹🇷 Turkish (Türkçe)
- 🇸🇦 Arabic (العربية)

Use the language selector in the top-right corner to change languages.

## Support

For technical issues or questions:
- Contact your state's technical administrator
- Report bugs on GitHub (if applicable)

## Best Practices

### Before SVS
1. Players submit their information early
2. Ministers review all submissions
3. Run auto-assignment
4. Make manual adjustments as needed
5. Export final assignments
6. Share with all alliances

### During SVS
- Players can update their information if resources change
- Ministers can quickly reassign if needed
- Export updated assignments as needed

### After SVS
- Keep export for records
- Thank players for participation
- Review process for improvements

## Security Notes

- Never share your minister password
- Change default passwords immediately
- Only share your FID with trusted state members
- Log out after using the admin panel
