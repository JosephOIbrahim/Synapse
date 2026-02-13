---
title: "MPM Train Wreck"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "train", "wreck", "destruction", "large_scale", "rbd", "debris"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=fwAuygMxk2w"
  series: "SideFX MPM H21 Masterclass"
  part: 16
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 473
duration_range: "0:15 - 20:11"
---

# MPM Train Wreck

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=fwAuygMxk2w)
**Presenter:** Alex Wevinger
**Part:** 16 of 18
**Transcript Lines:** 473

---

## Transcript

**[0:15](https://www.youtube.com/watch?v=fwAuygMxk2w&t=15)** It's now time to take a look at this Okay, so we have this very cool train asset. And um in this case, I'm also grabbing this other train asset just for the interior details. So I'm just going like to Frankenstein all of this detail inside of the other model because it doesn't really have interior detail. So then this is what I have at the end of those manipulations. So I have my train

**[0:47](https://www.youtube.com/watch?v=fwAuygMxk2w&t=47)** model and then if we go inside of it, we have those other interior details just so we see something cool when this train will break apart. So that is for our model and we do something similar for the train tracks. So I just use two different input model this guy and this guy and I merge them together just to take the best of both assets to create those train tracks. So off we go with those assets and we uh have our MPM setup for the simulation.

**[1:21](https://www.youtube.com/watch?v=fwAuygMxk2w&t=81)** So on one end I have my train. I'm putting that through this mpm source. Remember again, this is still the half resolution. So here on our npm container, we are still multiplying by this global particle separation multiplier. So just remember that you can set that back to one and you're going to get a lot more surface details. And on this npm source, we are grabbing the preset of metal. And uh I'm just adding a little bit of compression hardening. This usually will help at fracturing stuff. So, if you keep that to zero as the uh middle preset, you

**[1:52](https://www.youtube.com/watch?v=fwAuygMxk2w&t=112)** might get a lot of bending but not that much tearing. So, if you want things to be just more explosive and break apart easier, just add a little bit of that. And uh I'm also multiplying up this stiffness so that it uh held together a little more uh easier. And then in terms of type, usually we're always using volume, but in this case, I'm using surface just to scatter point on top of the mesh. surfaces and I'm also using this relax situation just to make sure that we have a good

**[2:23](https://www.youtube.com/watch?v=fwAuygMxk2w&t=143)** distribution of point and you don't have that many holes in there. Okay, good. And since we have a lot of panels that are near each other, I'm also enabling this fuse overlapping point just to make sure we don't have a lot of point unnecessary point on top of each other that will just cost a computation time for no additional details. And that's pretty much it for this guy. After that, we have our track here. And we are also adding a bunch of boxes because we're gonna have this train coming here and then starting to

**[2:54](https://www.youtube.com/watch?v=fwAuygMxk2w&t=174)** tumble on the ground here. And it will just like tumble for a long time on this ground here. And as we have more of this uh like those pointy colliders there, it's going to really help the train to just grip as it touches the ground and start uh rolling because we don't want to just have the the train sliding on the ground. We really want it to roll and we want this ground to grip and uh tear the metal surface as it's rolling over it. So, we're just adding all of those uh kind of synthetic colliders,

**[3:25](https://www.youtube.com/watch?v=fwAuygMxk2w&t=205)** but it's going to help a lot for the final animation that we're going to get. So, this is that. And also, you can see that in terms of friction, I'm using this varying friction new feature. So, here we look at the friction attribute. We can see that it ranges from 0.5 I think this is going to be for those rails here. So the rails are at 0.5 of friction but then everything else is at 1.25 and we can visualize this here. So we're using this uh friction create VDB from

**[3:56](https://www.youtube.com/watch?v=fwAuygMxk2w&t=236)** attribute. So we're using this friction attribute to drive a friction grid. And here we are visualizing it where we see that the low friction is applied to those rails and everything else is at high friction. And we have this friction grid being created. Cool. Um, so yeah, that's pretty much it. And then if I look at the solver, we have some visualization going on. And then I just increase the friction on the ground plane. And that's it. Everything else is at default. Almost too easy, right? Um,

**[4:28](https://www.youtube.com/watch?v=fwAuygMxk2w&t=268)** and then we have our simulation. So if I just look at what we have. So we have the train. It's starting like that. And then it hits here on the edge and it start to roll on its side. And as it's rolling, when it's catching those boxes and other details on the ground, it will start to uh to tear like that and create those cool openings. And if we run some more frames, we get more nice openings like this. And at some point, it will really start

**[4:59](https://www.youtube.com/watch?v=fwAuygMxk2w&t=299)** to break apart big time. So maybe if I go to Yeah, now this is like fully open and breaking apart. And this is going to reveal the seats that we add to our interior, which is pretty cool. Okay. And then this old branch is just going to be for the secondary. So we can like this is the same thing that I'm going over and over again. So we can go through it through it quickly. So here

**[5:30](https://www.youtube.com/watch?v=fwAuygMxk2w&t=330)** I'm creating this collider representation. I don't think I'm doing anything special. Yeah, just the default of the MPM surface. Then for this debris emission, I'm just uh reducing this minimum stretching. So I want more particles to be emitted. Everything else is at default. So we get this kind of Okay, just going to try to look at it better. So we have this kind of points that are being generated for our secondary emission of debris

**[6:00](https://www.youtube.com/watch?v=fwAuygMxk2w&t=360)** and this is what we get in terms of simulation here. The only detail that I'm doing is I don't want to render those debris as points. I actually want to take some small parts of the train and and sense them on those particles. So the one thing that I'm doing is here if we dive inside this uh secondary sim. Okay, I'm I'm kind of uh controlling the orientation of those points. So here the the code that is going on is

**[6:35](https://www.youtube.com/watch?v=fwAuygMxk2w&t=395)** that um I'm defining um I'm defining an axis that will be perpendicular to the velocity and then so with those uh this cross product and this up vector because I want the debris to be rolling in the direction of uh the velocity right think about a wheel or a sphere that is rolling in one direction touching the ground. I want this kind of motion. Okay. So here I'm computing the perimeter of the particle. So it's basically

**[7:07](https://www.youtube.com/watch?v=fwAuygMxk2w&t=427)** our formula from math. It's like 2 * pi * the radius. And here our radius is the half of the pc. So here I'm computing. So how much given the distance I'm traveling within a single frame, how many uh complete rotation I have. So how much of this uh perimeter I'm I'm traveling in space and then I'm multiplying that by 2 pi which is in the radiant the the size of a full u a full rotation if you will. And finally since this could be a little too fast

**[7:38](https://www.youtube.com/watch?v=fwAuygMxk2w&t=458)** sometimes like if you do it accurately like a wheel on the ground it might be spinning like crazy when it's a flying debris. So I'm just multiplying that by 25. So this is a little bit artificial but it's because things are just like spinning too fast at some point. uh and then yeah I'm applying that as a rotation to this uh identity matrix and I will be uh storing that well in fact I'm computing the angular velocity here and I'm storing that in this www attribute because if I use the W attribute well this guy is going to

**[8:09](https://www.youtube.com/watch?v=fwAuygMxk2w&t=489)** try to use it so this pops will apply this angular velocity to the orient attribute so we want our own naming thing because we don't want this popsolver to be handling the the orientation for So here we have our rotation that we apply to this orient attribute. So we are fully controlling orientation and angular velocity here. Again we're handling our collision there. And when we're out of this I'm remapping this W attribute to just W for the angular velocity attribute so we can use

**[8:41](https://www.youtube.com/watch?v=fwAuygMxk2w&t=521)** it in rendering. Then I'm caching that. And here I'm splitting. So this is our simulation that we're looking at and I'm just splitting it into two branch. So some of it are going to be used as sparks as we see here. So we want like some sparks uh when the metal start hitting the ground and most of it is going to be used as just debris and stencing and uh here I'm doing some additional pruning based on on frames. So you can dive inside and see okay like I don't want any debris to be visible before this frame. So everything that

**[9:14](https://www.youtube.com/watch?v=fwAuygMxk2w&t=554)** was existing at this frame 47 I want it gone. And here I just want to reduce the amount of debris. So anything that exists at frame 58 I just want to keep uh 75%. So I'm rem removing 25% here. And whatever I find here I delete. So I delete 75% of what is present at frame 58. So a little bit weird. And this is definitely like manual adjustment. you can do uh for your own taste, but I just set it up this way so you can know this the settings that I I've been using for

**[9:45](https://www.youtube.com/watch?v=fwAuygMxk2w&t=585)** the original shot that I showed at the beginning of this master class. Good. So, this is for the secondaries and uh then we have our retargeting. So, this is the important stuff. Um okay, one problem that we're going to face is this tool set. to this MPM post structure and npm deformed pieces. It not it's not really designed to deal with changing point count, right? Because it's always like looking at the first frame and the last frame and it's it's going through the timeline and

**[10:16](https://www.youtube.com/watch?v=fwAuygMxk2w&t=616)** comparing uh point positions. So for that because uh our original sim if we go back to the mpm sim here you can see that our container here it's deleting the points. So any points that are going outside of this bonding box are going to be pruned out and this is problematic. So we just have to bring them back. So if I look at the sim that we have, I'm Okay, this is an example. So you can see

**[10:52](https://www.youtube.com/watch?v=fwAuygMxk2w&t=652)** So at frame like around between 140 145 it's disappearing. Okay. So we have to loop through all the frame range and just make sure that when it's deleted it's just going to be frozen in space. Okay. So this is what this uh simulation is doing here. So I'm just instead of running it here, I can just look at the cache version. So you can see what's happening. So the point will just like be frozen in space. And this is not like our final um this is not going to be used for rendering. This is just used such that those two tools can work properly to just make sure that we have

**[11:22](https://www.youtube.com/watch?v=fwAuygMxk2w&t=682)** a consistent point count. And this is what we have. So if I go like at the beginning, we have our point count here. So, uh, 144,639. And if we go here, exact same number. So, this is perfect. As opposed to here, we have a changing point count. So, 139. A lot of points are being blasted from the MPM SIM. So, when we have that in place, we can do the MPM fracture. And in this case, I'm just going to show you

**[11:52](https://www.youtube.com/watch?v=fwAuygMxk2w&t=712)** So, this is the kind of fracture that we get. And we can still look at this guy, but I'm just not going to compute the fracture because I can't remember exactly how much time it's taking, but it's quite slow. So, if we just look at the different guides that we have, I'm going back in automatic cooking. And here P selection, I can show guide. So, everything that is red is not going to be fractured because it's considered too much of a small part according to this

**[12:25](https://www.youtube.com/watch?v=fwAuygMxk2w&t=745)** number. Then if we go to fracture points uh you can see that there are a lot of fill points. So all of those white points those are points that has nothing to do with the MTM simulation itself. So those are artificial points that are being added just to make sure that the model can um have enough resolution to uh to be flexible. Right? So if if all of this piece uh is being not it's not tearing in any at any point but it's being deformed a lot. We still want the geometry to deform gracefully. We don't

**[12:56](https://www.youtube.com/watch?v=fwAuygMxk2w&t=776)** want like a lot of linear patches that are kind of that look like broken polygons. We want things to be able to be like smooth and curved. So, for that reason, we are adding a lot of filler points. But right now, I'm considering that maybe uh there are just way too many filler points. So, maybe if you try to recreate this scene, I would encourage you to try to reduce this amount of filler points because I think it's probably a little excessive right now. Anyways, so this is the setting for the filler point and we have our MPM point that we're seeing here. And again,

**[13:27](https://www.youtube.com/watch?v=fwAuygMxk2w&t=807)** we uh we remember from the uh from when we were in the basic part of this course that we are using this align fracture to stretch points. So if we remove that, those are actually the points that have detected a fracture. Okay. So if I look at here, if I want a fracture here, the center of my fracture points should be around on each side here and here. And then if I click that, this is exactly what I get. So I have a line of points here and a line of points here and my fracture is going to be centered right here. This is what I want. But for other regions like here, we have a big patch of points that is being completely

**[13:59](https://www.youtube.com/watch?v=fwAuygMxk2w&t=839)** blasted by this toggle. And so of course, yeah, it's going to place the fracture here, here ear, and ear, but it might depending on the type of look you're after. This might not be the proper placement of those cent point for fracturing. So maybe you would prefer this. Um, yeah, really depends on your taste. um when you have like a line of points like here um this uh attribute works perfectly well you will well okay this is not a great example I think it was probably like beyond below the

**[14:31](https://www.youtube.com/watch?v=fwAuygMxk2w&t=871)** threshold but let's pick a let's pick right here okay so when we have a line here that is going to be considered as fracturing and you flip to this mode and you have those two rows of point on each side. This is going to work really really well. But when there's a bigger patch that is identified as fracturing like what we had at the front here, this is less obvious what is the best fracture mode. So it could be with this toggle on, with this toggle off, it's

**[15:01](https://www.youtube.com/watch?v=fwAuygMxk2w&t=901)** really up to you to decide what you want. Anyways, enough talking about those fracture points. So this is what we have in the end. And uh I'm not going to show the cutter geometry because uh like it's there's just too much stuff overlapping. So we don't really see anything but um yeah apart from that yeah that this is all to we're just adding interior details because we want more geometric details but this is all kept to default. Uh here we have I think

**[15:33](https://www.youtube.com/watch?v=fwAuygMxk2w&t=933)** if I go back to the default. So yeah we have reduced this value quite a bit and um I think those are also close to default but decrease a little bit because we have a lot of filler points. Good. So now I'm just going to revert Good. And then we have our fracture model.

**[16:04](https://www.youtube.com/watch?v=fwAuygMxk2w&t=964)** And we can now look at the if we pick an interesting frame. So let's say 130. We It's going to take a little bit of time And now we have our fracture train in context. And I can just hide the wireframe.

**[16:34](https://www.youtube.com/watch?v=fwAuygMxk2w&t=994)** And if you look like uh if you look at the region like this where we have a lot of metal tearing. I just want to show you that. Okay, we're basically looking at uh we're just using almost everything at default. We're computing the velocity here. This is at default. This is also a default. And we are transferring this deleted attribute that we have stored here because we need consistent point count for this part. But after that, we're just going to prune those pieces that were deleted because we don't want like floating pieces to be hanging in there. And this is what we're going to use for

**[17:05](https://www.youtube.com/watch?v=fwAuygMxk2w&t=1025)** rendering. So I'm transferring this attribute. And then I just want to show you this uh closed gap. So if I disable this, take a look at how it's going to affect this region. So again, it's Okay. And then I can zoom in on some of the

**[17:40](https://www.youtube.com/watch?v=fwAuygMxk2w&t=1060)** So, we can see like a lot of those cracks here that are really unnatural for metal tearing. And now if I bring back this closed gap, all of those small gaps here are going to be filled. And it's going like it's not going to be perfect for sure, but it's going to be a And this is what we get with this option toggle down. So yeah, for metal tearing, really important to use this close gap feature.

**[18:12](https://www.youtube.com/watch?v=fwAuygMxk2w&t=1092)** And after that, we have just some debris preparation that we're using for rendering. So here I'm grabbing our train and now I'm extracting all of the fine pieces, all the small pieces of the train. Then I'm just packing that and preparing that for debris emission. Okay, so those are are ready for instancing. I'm doing same thing for some rocks. So these are the rocks that we've been using in the creature breach scene. And here I'm just like packaging them uh again for instancing.

**[18:43](https://www.youtube.com/watch?v=fwAuygMxk2w&t=1123)** Here I'm creating uh this is going to be just static rocks. So a bunch of points that I'm going to instance some rocks at render time just to make the the landscape more interesting. And that's it. And then if you go to Solaris here uh I have those uh like the secondary debris of the train on uh one side here I'm bringing those debris that we just showed and here I'm bringing the uh the debris points. And if I go back to subs just to show you those. So these are the secondary points that we're looking at.

**[19:14](https://www.youtube.com/watch?v=fwAuygMxk2w&t=1154)** And the one thing that you have to pay attention for this instancing to work properly is what is being defined here. So I skipped over this one a little quickly. So here I have just a bunch of manipulation that I'm doing on the pcale to try to get a cool distribution of debris. And this is what's important for debris and sensing. So we grab how many debris we have. So this debris count of over a thousand is coming from here. So how many pack primitives pack debris I have and then I'm going to set an index.

**[19:46](https://www.youtube.com/watch?v=fwAuygMxk2w&t=1186)** So each of the this each of the points here are going to have a unique not a unique but an index referring to a unique piece in uh the debris collection. So this is important for instancing. And then I'm also grabbing this rest attribute probably for shading. And here I'm just ramping down the emission from frame 160 to frame 90 from full emission to no emission at all. And yeah, that's pretty much it for this
