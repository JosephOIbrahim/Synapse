---
title: "MPM Building Attack"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "building", "attack", "destruction", "large_scale", "fracture", "collapse"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=beyRxMYzwsk"
  series: "SideFX MPM H21 Masterclass"
  part: 17
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 542
duration_range: "0:16 - 23:07"
---

# MPM Building Attack

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=beyRxMYzwsk)
**Presenter:** Alex Wevinger
**Part:** 17 of 18
**Transcript Lines:** 542

---

## Transcript

**[0:16](https://www.youtube.com/watch?v=beyRxMYzwsk&t=16)** And let's finally take a look at this last scene, this building attack setup. Okay, so uh I have a disclaimer first. So this uh model is unfortunately not going to be shared with the masterclass. We are not allowed to share this model because it's coming from Kit Bash. And yeah, I made the mistake of uh using this asset for this uh scene. But uh I will tell you that you can pretty much take any building asset from Sketch Fab

**[0:47](https://www.youtube.com/watch?v=beyRxMYzwsk&t=47)** anywhere that they distribute free model and it should pretty much do the same. It's not like this building is particularly good for destruction. This is modeled exactly the same as all the other models that you can find on the internet. So like most things that are going to be visible are being modeled, but everything else that you don't see is is not modeled, right? So you don't have convex holes. You don't have uh anything that is closed. So you pretty much any model that you can find in the internet, you're going to have to fight with it to make sure that it's like a

**[1:17](https://www.youtube.com/watch?v=beyRxMYzwsk&t=77)** watertight closed volume that you can use for fracturing. So yeah, the this model is not different than uh any of those other models on the internet. So that being said, first step is to start with the model that is not usable for destruction and make it usable for destruction. So here I'm doing a couple of just like fusing, trying again to close the model as much as possible. And here you can see pretty much everything that I'm doing to make it

**[1:48](https://www.youtube.com/watch?v=beyRxMYzwsk&t=108)** watertight. I'm also here building some kind of internal structure to it. So uh in the end you get this VDB uh building. This is the end result that we want. So we want something with a volutric representation where it's clear what is inside, what is outside. Everything has a thickness and this is ready for fracturing more or less. We need to transfer the UVs. But I mean this is a volume that we can fracture. And if you look inside of it, so if you dive here, you can see that I've added those pillars. Yeah, it's not very clear, but

**[2:20](https://www.youtube.com/watch?v=beyRxMYzwsk&t=140)** yeah, I've added those internal pillar to hold the ceiling. Otherwise, like if I don't add this geometry, everything is going to collapse on itself. So, you have to be a little bit of a civil engineer and make sure that this structure is going to uh hold on itself. [snorts] So yeah, when we're done with that, it's just a matter of bringing the original asset with all of our pretty UVs and just transfer that over to this um building representation

**[2:52](https://www.youtube.com/watch?v=beyRxMYzwsk&t=172)** and we get this clean building. So we both have something that can be fractured and we also have transferred over the UVs. Great. So yeah, all these steps you can just redo them with another building with similar kind of visual attributes and you can follow along after that for the the rest of the setup. It should be pretty much the same thing. Then uh here we have our MPM scene, MPM simulation setup. So first thing we just grab the model. Let's go to the

**[3:24](https://www.youtube.com/watch?v=beyRxMYzwsk&t=204)** first frame. And here we just generate a bunch of points from it. as usual. And this is just the concrete preset. We have increased like double the stiffness here. And that's it. Everything else is at default. I'm very uh on original on that. Then uh you have this noise attribute that I'm adding to the stiffness. Very similar like the same setup that I'm just always doing here. You see like if I display it as color, you see uh the noise that I'm creating. And I'm just going to multiply the stiffness with that just to make sure I

**[3:56](https://www.youtube.com/watch?v=beyRxMYzwsk&t=236)** get more variation in the sim. And that's it. Um, okay. For the projectile, because I want to have like some projectile coming in and and crashing onto this building. And there's just a little bit more setup for that. So, first thing, I'm grabbing the part of the building that I want to be hit by some projectile. Then, I'm just using a scatter to define where I want those projectile to it. And then what I do is I uh first define when things are going to it. So I want those it to happen between frame 48 and then

**[4:29](https://www.youtube.com/watch?v=beyRxMYzwsk&t=269)** three times frame 48. Um so like right about right before frame 150 uh we should have the end of our collision happening. And then I'm just going to backtrack those collider like backward in time. So I know when they are supposed to hit. So I just have to push them um to push them out using their velocity that they are going to have when they hit. And I'm also accounting for the gravity applying the gravity on each frame here. So this should be our distribution of

**[5:02](https://www.youtube.com/watch?v=beyRxMYzwsk&t=302)** collider uh in space on the first frame and then as we are moving forward in time at some point those are going to be iting. So just want to show you. So whenever this point like one of those points is hitting the building, this is supposed to be synced with this in frame uh with this it frame that we defined here. And this is what we have. And don't worry about like the trajectory look weird because it's going back up. And this is just because of how I'm [clears throat] accounting for the gravity here. This is

**[5:33](https://www.youtube.com/watch?v=beyRxMYzwsk&t=333)** perfectly fine. We don't care about the second half of the animation because after those points when they are like coming back up here, they are no longer using this information. So we only care about this part of the animation. Then I need to isolate when those points are going to uh be considered as mpm points. So I'm using this domain box. So whenever they enter in this box, I'm grouping them. And then here I'm detecting the first frame that they

**[6:04](https://www.youtube.com/watch?v=beyRxMYzwsk&t=364)** enter this box. And this is when we're going to emit those points as MPN particles in the sim. And you can see like as I'm moving on the timeline here, you can see those points like flickering on and off because they they have to be present only on one frame. And after at this specific frame, I'm copying a sphere on them. And then I'm sourcing some MPM particles like we see here. And this is a continuous emission. So whenever I have this collider coming in this bounding

**[6:34](https://www.youtube.com/watch?v=beyRxMYzwsk&t=394)** box, this is when this is going to be emitted. Good. And for the solver itself, uh there's everything is at default. Yeah, we have some visualization going on and we are uh modifying the attribute that we are going to output. But apart from that, the one thing that you need to be uh careful about is this thing assume unchanging material properties. So the reason why we have this unchecked because this is usually checked as an optimization to make the simulation

**[7:04](https://www.youtube.com/watch?v=beyRxMYzwsk&t=424)** faster. But here we have purposely unchecked it because the simulation start with just the building in there. Right? So the NTM solver is going to say okay I have this material that I'm simulating with this amount of stiffness. But then at some point we have those collider coming in and if you look at their attributes. So if I do just look at this uh material tab here you can see the stiffness is very very high and also the density is higher. So this combination of material attribute is going to make the colliders like those projectile more complex to

**[7:36](https://www.youtube.com/watch?v=beyRxMYzwsk&t=456)** simulate than the building itself. So as those are introduced in the simulation if they are not taken into consideration uh for to add more substeps to stabilize the sim the simulation is going to explode. So having this checkbox uncheck means that on every single frame the solver is going to assume that some things could be changing with the definition of the materials and it needs to reevaluate. Okay, do I have something that is suddenly more stiff in the simulation that I need to take into account in order to u maybe increase the

**[8:06](https://www.youtube.com/watch?v=beyRxMYzwsk&t=486)** amount of substeps that I'm doing to keep things stable. So yeah, this is just something to keep in mind when you are continuously adding uh new types of material in your sim. So this is pretty much it. And now if we look at the simulation that we have and I'm going back to auto update, we have something like this where we have our collider hitting the building and

**[8:38](https://www.youtube.com/watch?v=beyRxMYzwsk&t=518)** Like so. Okay. So far so good. Um, after that we get into a little bit of preparation before we actually do the retargeting of the dynamics onto the uh the original asset. So, first thing I'm splitting this um simulation into the building points and the projectile points. For the building point, the one thing that I'm doing is since I'm there's a little bit of vibration in the simulation between the first frame and the frame

**[9:08](https://www.youtube.com/watch?v=beyRxMYzwsk&t=548)** that things are going to start hitting the model. So here I'm just like freezing those two frames and I'm just lurping. Uh I'm just doing like a linear interpolation between the first frame and this frame 35 just to remove a little bit of the vibration that we're seeing in the first couple of frames. That's it. You can also just freeze frame 35. It's going to work just as well. But in this case, yeah, I I just did that solution just to show you uh one of the little tricks that you can do to remove this. And uh regarding the projectile

**[9:40](https://www.youtube.com/watch?v=beyRxMYzwsk&t=580)** themselves, what I'm doing is um so you remember from if you've looked at the tutorials in the sequence from the um train example, we need to have a consistent point count, right? So if the point count is changing over time, we're going to have some issue for retargeting. So this is exactly what we are fixing here. So we have our points and if we look at them uh maybe more at the beginning, we will see that they are appearing, right? So if I go on okay on this frame so between frame

**[10:13](https://www.youtube.com/watch?v=beyRxMYzwsk&t=613)** 56 and 57 we see that this uh projectile is appearing. So we want this to be constant. So here we're going to start from frame 110. It happens to be the frame where all the projectile have been emitted. And then we're going to solve um from like we reverse the time. to we resolve from 110 to frame zero or frame one just to gather their rest position. So if I look at what is being cached here. So now we're no longer having

**[10:43](https://www.youtube.com/watch?v=beyRxMYzwsk&t=643)** we're no longer having a changing point count because whenever the the points are not existent at least they are static in space before they are emitted in the MPM simulation and then when they start well okay in this case this is like a a static frame uh and here okay here we are just like okay this is this branch here is the branch where we have the points like being emitted and then being animated in this branch. We

**[11:14](https://www.youtube.com/watch?v=beyRxMYzwsk&t=674)** are just at the moment making sure that the the points that are not existent in in this branch are existent here. So when the the points have not appear in this branch, they will be static at rest space like at emitted space here. This is where we're doing the animation. Okay. So if I'm looking here, we have all those points that have been emitted and here those are the point at rest space before they are emitted. And here uh with this node we're just grabbing what would be the uh velocity that the the points are using when they are

**[11:46](https://www.youtube.com/watch?v=beyRxMYzwsk&t=706)** emitted and we use that to backtrack the particle in time. So you can see that all of those points that we're seeing here the mpm points uh we're just taking their emitted position and we're backtracking them linearly in space. And in this case I'm not even using the gravity. So this is not really that accurate but it's not really going to show in this case because of the the camera position but yeah this is just a linear interpolation or more like extraolation using the velocity at emitted time and

**[12:17](https://www.youtube.com/watch?v=beyRxMYzwsk&t=737)** backtracking the point in space. So then you see that on this branch as I was saying the points are going to disappear as they are emitted. So if we push that the points are disappearing from this branch and are appearing on this branch and then when we merge them together we have just like a smooth animation uh that extrapolate the particles back in time but we haven't we didn't need to simulate all of those mpm points and as they are going forward in time they are transitioning from this uh linearly

**[12:47](https://www.youtube.com/watch?v=beyRxMYzwsk&t=767)** extrapolated uh position to the actual animated uh simulated mpm trajectory. Okay. So this is for this branch just to make sure that we have a static point count and in this branch here we are basically defining the geometry that we're going to use for rendering. So same thing as before we are having all of our points at rest or emitted space and then we copy some geometry on it. Then we play with the UVs a little bit just to add some uh variation. We add some noise to the surface just to make

**[13:21](https://www.youtube.com/watch?v=beyRxMYzwsk&t=801)** the the sphere a little bit imperfect. And then we add back our animation so they can be brought back to the first frame because we need those two branches like the MPM points and the geometry that you're using for render. We need them to be synced uh for the first frame. Good. Then when this part is done, we're getting into fracturing and retargeting the dynamics of the MPM simulation onto those assets. So here

**[13:52](https://www.youtube.com/watch?v=beyRxMYzwsk&t=832)** we have our assets. Here we have our MPM points and we're basically like looping over each of them one by one. So if I just select this guy here and we just have one single projectile. We're grabbing the MPM point and we are fracturing this guy uh here. Don't think this has a lot of fracture. Maybe I can put a exploded view just to see a little bit better. Okay. Yeah, it has a decent amount of fracture points. And

**[14:24](https://www.youtube.com/watch?v=beyRxMYzwsk&t=864)** we can even like uncheck fracture and just look at those uh fracture points guides. Okay, so we can see that this one has very little uh like there's just a small impact here and the rest of the fractures are defined by those filler points and again there's nothing special here. So I just okay here I'm reducing this uh point separation number so it will add more filler points and I'm also reducing this m max distance. So this m max distance is the distance between the filler points and the area where we have

**[14:56](https://www.youtube.com/watch?v=beyRxMYzwsk&t=896)** mpm points that are defining fracture pieces. So as you reduce this you're going to get those points like closer and closer. I can even show you. So if you put that to okay maybe this is too much. So see now we have the points uh this those fitter points are restricted to be very close to the mpm fracture points but we can extend that and we're going to keep the settings that I had originally but I just want wanted to show you that um so yeah I'm going to

**[15:27](https://www.youtube.com/watch?v=beyRxMYzwsk&t=927)** flip back to manual mode bring this back to the original settings and yeah we're adding interior details as well to have If I go back to auto update and look at this exploded view, you can see those interior details here. So, it's not just like a flat panel for all of those fractures area, which is good. And yep, that's pretty much it for this guy.

**[16:00](https://www.youtube.com/watch?v=beyRxMYzwsk&t=960)** And the one thing to keep in mind also is this expression here. So here you have like fracture name space. We are also gathering the iteration of this for loop and this is to make sure that we don't have name clashes. So here if I middle click just to show you. So we have the name of this projectile fracture and we have an underscore for just to make sure that each of those projectile that are being fractured have a unique name so we don't have name clashes when we want to retarget later. And that's it for the projectiles.

**[16:33](https://www.youtube.com/watch?v=beyRxMYzwsk&t=993)** Um then we can just retarget them. This is just using everything as default. If I look at the final projectile retarget and I move a little bit in time, we can see that as those projectiles are either hitting the building or the ground, they are breaking and we have cool details like

**[17:12](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1032)** Cool. And now for the building itself. Again, I'm just going to uh uncheck this perform fracture so we can actually look Flipping back to auto update. And here you can see the points that we're using to do the fracturing. Here I have increased a little bit the fuse distance so we don't have such small uh fracture pieces. I've also increased this minimum stretching. So we don't want to have too many uh fracture pieces

**[17:43](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1063)** generated with low JP attribute. And I'm using this align fracture to stretch point. Again for concrete material you can really uncheck it. You can test with and without depending on what you want. it will give you different looks and uh one or the other could work for concrete. There are no like perfect recipe. And here you can see that we're definitely benefiting from this max distance. So because we're using that, you see that those filler points are only concentrated near uh areas that are going to be fractured from the npm simulation. So all of those areas are

**[18:14](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1094)** not being fractured. And this is really helping us in keeping this model uh like manageable in terms of memory and computation. So that is good. And here we are uh increasing or decreasing the amount of resolution that we're going to add to those internal faces. Again, just to keep the amount of memory uh manageable. And yep, that's pretty much it. Then when we look at the final building being being retargeted,

**[19:07](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1147)** So this is our MPM simulation. And now we switch to our geometry representation and we have all of all of our UVs and everything to render with lookdev applied which is exactly what we want. Good. And then again we have our uh secondaries that we're always doing. So uh here I think I'm just using the mpm surface as default.

**[19:37](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1177)** Yeah, exactly. Nothing special happening here. Um, I'm going through this MPM debris source again. I don't think there's anything special. So, I'm just increasing those limits here. I don't want too many points to be emitted. Uh, this is yeah, we have reduced this threshold. So we want to uh replicate less based on the speed and we have also reduced this guy here to have less replication also

**[20:08](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1208)** based on the stretching attribute. And here we are initializing this random variant. I think we're also doing the same thing for the train example but I and we get something like that for our emission of secondary debris. Again, we need to we're varying the P scale to get as much randomness in the distribution of the debris as possible. And we are setting our uh debris index for instancing in Solaris. And here I

**[20:39](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1239)** I'm also setting a UV attribute that I'm going to use uh for rendering because I want to be sampling the textures um with each of those debris to have like interesting color distribution on these. And for the debris itself that I'm going to uh that I'm going to instance, those are just like I'm taking a sphere that I'm fracturing and it's generating multiple like low resolution bits like that. This is what I'm going to use as debris instances. Very simple stuff. And

**[21:10](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1270)** for the secondary debris again I'm managing the collisions here. uh I am computing the packing of the point cloud such that like I'm I'm always repeating myself about that but like the points that are really densely packed they are not going to obey air resistance and wind but if you're like a lonely point that is not with a lot of neighbors around it you're going to be more catching in the wind and more uh moved around by this wind this is why I'm doing this those two nodes are working together and we are also um managing the

**[21:40](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1300)** rotation with a setup that is exactly the same thing that we had for the the train scene. So just to make sure that as debris is moving forward in space, Good. And here we can visualize our secondary simulation. And everything that you see in red is considered like highly densely packed. So this is not this is going to ignore the wind. And everything that is this purple color is going to catch a lot more in the wind.

**[22:12](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1332)** Sorry, I'm in a I wasn't in auto update mode. So, you can see like in a frame like this, everything in red is just completely ignoring the wind and air resistance. And those small isolated bits in purple are catching in the wind more. And this will give you like a cool distribution for the secondary particles. And that's it for this scene. And this concludes our look at those practical

**[22:57](https://www.youtube.com/watch?v=beyRxMYzwsk&t=1377)** So this concludes our master class of the updated MPM solver in H21. I really hope that you're going to enjoy those new feature in new nodes and I can't wait to see all of the cool visuals you're going to create with that. Thank
