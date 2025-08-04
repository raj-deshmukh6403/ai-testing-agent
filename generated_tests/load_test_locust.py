
from locust import HttpUser, task, between
import random
import json
import time
import logging

logger = logging.getLogger(__name__)

class WebsiteUser(HttpUser):
    wait_time = between(1, 5)
    
    def on_start(self):
        """Called when a user starts"""
        self.client.headers.update({
            'User-Agent': 'LoadTest-Agent/1.0'
        })
        logger.info(f"User started")
    
    def on_stop(self):
        """Called when a user stops"""
        logger.info(f"User stopped")


    @task(3)
    def basic_navigation(self):
        """Navigate through main pages"""
        try:
            
            # Visit homepage
            
            with self.client.get("/", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Got status code {response.status_code}")
                    logger.warning(f"GET / returned {response.status_code}")
            
            
            
            
            # Think time
            
            time.sleep(2)
            
            
            
            
            
            # Random think time
            time.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            logger.error(f"Error in basic_navigation: {str(e)}")



# Usage:
# locust -f generated_load_test.py --host=https://your-target-site.com
# locust -f generated_load_test.py --host=https://your-target-site.com --users=50 --spawn-rate=5 -t 300s