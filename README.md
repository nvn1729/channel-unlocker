# channel-unlocker

Channel Unlocker is an Alexa skill for unlocking channel content on a Roku. It supports unlocking the Disney and Nick Jr channels using DIRECTV NOW as a TV provider. 

Example conversation:

```
You: "Alexa, tell Channel Unlocker to unlock Disney."
Alexa: "Ok, what's the activation code?"
You: "ABCDEFG."
Alexa: "Done. Goodbye!"
```

You can package up the server side code using `./create_lambda_package.sh`, and then deploy the package in AWS Lambda. When configuring the Lambda function, set the `USERNAME` and `PASSWORD` environment variables to the credentials of your TV provider. You can optionally use the AWS Key Management service to encrypt your credentials. The Lambda function should be attached to a VPC with external network access. Fork to support your own channel(s), TV provider, or device!

More details are available in this [post](https://naveensunkavally.com/2018/07/31/an-alexa-skill-for-unlocking-channel-content-on-my-roku/).

This source code is released under the Apache v2 License.

&copy; 2018 Conversant Design LLC
