# AWS Backend Setup Instructions

To host your news site's data and automate updates for free, follow these steps to set up AWS S3 and Lambda.

## 1. AWS S3 (Storage)

1.  Log in to the **AWS Console** and search for **S3**.
2.  Click **Create bucket**.
3.  **Bucket name**: `personal-site-news-yourname` (must be globally unique).
4.  **Region**: Choose one close to you (e.g., `us-east-1`).
5.  **Object Ownership**: Keep default (**ACLs disabled** / Bucket owner enforced). This is the AWS recommendation.
6.  **Block Public Access settings**: Uncheck **Block all public access**.
    -   Acknowledge the warning.
7.  Click **Create bucket**.

### Configure Public Access (Bucket Policy)
Since ACLs are disabled, we use a Policy to make files public.

1.  Click on your new bucket > **Permissions** tab.
2.  Scroll to **Bucket policy** and click **Edit**.
3.  Paste this JSON (replace `YOUR_BUCKET_NAME` with your actual bucket name):
    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
            }
        ]
    }
    ```
4.  Click **Save changes**.
8.  Click on your new bucket > **Permissions** tab.
9.  Scroll to **Cross-origin resource sharing (CORS)** and click **Edit**. Paste this JSON:
    ```json
    [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": []
        }
    ]
    ```
    *(Ideally, replace `*` in AllowedOrigins with your actual domain `https://news.gattani.ca` for better security).*

## 2. AWS Lambda (Automation)

1.  Search for **Lambda** in the AWS Console.
2.  Click **Create function**.
3.  **Function name**: `fetch-news-stories`.
4.  **Runtime**: `Python 3.12`.
5.  Click **Create function**.

### Add Code & Dependencies
Since we use external libraries (`feedparser`, `textstat`), you need to create a deployment package. I have created a script to do this for you.

1.  Open your terminal in the `backend` folder.
2.  Run the build script:
    ```bash
    chmod +x build_lambda.sh
    ./build_lambda.sh
    ```
3.  This will create a `lambda.zip` file.
4.  In the AWS Lambda console, find the **Code** tab.
5.  Click **Upload from** > **.zip file** and upload `lambda.zip`.

### Configuration
1.  Go to **Configuration** > **Environment variables**.
2.  Add variable: `S3_BUCKET_NAME` = `personal-site-news-yourname`.
3.  (Optional) Add variable: `RSS_FEED_URL` = `https://your-preferred-feed.com/rss`. (Defaults to CBS News if not set).
4.  Go to **Configuration** > **Permissions**.
4.  Click the Role name to open IAM.
5.  Click **Add permissions** > **Attach policies**.
6.  Search for `AmazonS3FullAccess` (or create a stricter policy) and attach it.

## 3. Automation (EventBridge)

1.  In the Lambda function overview, click **Add trigger**.
2.  Select **EventBridge (CloudWatch Events)**.
3.  Select **Create a new rule**.
4.  **Rule name**: `weekly-news-trigger`.
5.  **Schedule expression**: `cron(0 12 ? * MON *)` (Runs every Monday at 12:00 UTC).
6.  Click **Add**.
