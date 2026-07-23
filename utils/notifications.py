"""
Notification Manager — Push notification infrastructure.

Ready for Firebase Cloud Messaging integration.
Current implementation is a scaffold: validates payloads and logs.
"""

import json
import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass
class PushNotification:
    title: str
    body: str
    icon: str = "/static/icons/icon-192x192.png"
    badge: str = "/static/icons/icon-72x72.png"
    tag: str = ""
    data: dict | None = None
    url: str | None = None


def send_notification(subscription: dict, notification: PushNotification) -> bool:
    """
    Send a push notification to a subscribed client.

    Args:
        subscription: dict with 'endpoint', 'keys' (p256dh, auth)
        notification: PushNotification instance

    Returns:
        True if sent, False otherwise

    TODO: Implement with Firebase Admin SDK or Web Push Protocol.
          Requires VAPID keys in environment config.
    """
    payload = {
        "notification": asdict(notification),
    }

    logger.info(
        "[NOTIFICATION] Would send to %s: %s",
        subscription.get("endpoint", "unknown"),
        json.dumps(payload, ensure_ascii=False),
    )

    return True


def send_notification_to_user(
    user_id: int,
    title: str,
    body: str,
    url: str | None = None,
) -> bool:
    """
    Send a notification to a specific user.

    Queries the user's push subscriptions from the database
    and sends to each.

    TODO: Implement database subscription lookup and fan-out.
    """
    payload = PushNotification(
        title=title,
        body=body,
        url=url,
    )

    logger.info(
        "[NOTIFICATION] Would notify user %d: %s",
        user_id,
        json.dumps(asdict(payload), ensure_ascii=False),
    )

    return True


def broadcast_to_school(
    slug: str,
    title: str,
    body: str,
    url: str | None = None,
) -> bool:
    """
    Send a notification to all users in a school with active subscriptions.

    TODO: Query all active push subscriptions for the given school slug.
    """
    payload = PushNotification(
        title=title,
        body=body,
        url=url,
    )

    logger.info(
        "[NOTIFICATION] Would broadcast to %s: %s",
        slug,
        json.dumps(asdict(payload), ensure_ascii=False),
    )

    return True


def save_subscription(db, slug: str, user_id: int, subscription: dict) -> bool:
    """
    Save a push subscription to the database.

    TODO: Create push_subscriptions table and implement storage.
    """
    logger.info(
        "[NOTIFICATION] Would save subscription for %s / user %d",
        slug,
        user_id,
    )
    return True
