# mopidy-soundcloudsimple

This is simple SoundCloud backend for Mopidy V3.

It gives you access the tracks of the users you follow. The recent 100 tracks will also be provided as a "stream" (Not to confuse with Soundscloud's own "Stream" feature)

# install
```
cd ~
git clone https://github.com/magcode/mopidy-soundcloudsimple.git
cd mopidy-soundcloudsimple
sudo python3 setup.py develop
```

# uninstall
```
cd ~/mopidy-soundcloudsimple
sudo python3 setup.py develop -u
rm -rf ~/mopidy-soundcloudsimple
```

# configuration in mopidy.conf

~You need an `auth_token`. Easiest way is to use the guide from the [original SoundCloud extension](https://mopidy.com/ext/soundcloud/)~

You need a `client_id` which you can get from [SoundCloud](https://soundcloud.com/you/apps). You may also look around and use an existing one.

The user_id is your soundcloud userID. The easiest way to get it is calling [view-source:https://soundcloud.com/stream](https://soundcloud.com/stream) and search for `soundcloud:users:`

```
[soundcloudsimple]
enabled = true
auth_token = <your personal auth_token>
client_id = <your client_id>
user_id = <your user_id>
```
