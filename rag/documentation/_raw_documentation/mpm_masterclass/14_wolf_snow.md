---
title: "MPM Wolf Snow"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "wolf", "snow", "character_interaction", "deformation", "particles"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=JUcON39F7zE"
  series: "SideFX MPM H21 Masterclass"
  part: 14
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 387
duration_range: "0:11 - 16:01"
---

# MPM Wolf Snow

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=JUcON39F7zE)
**Presenter:** Alex Wevinger
**Part:** 14 of 18
**Transcript Lines:** 387

---

## Transcript

**[0:11](https://www.youtube.com/watch?v=JUcON39F7zE&t=11)** Okay, let's now take a look at this wolf Okay, so first thing that we have in this scene is this wolf. And I think it was stolen from another uh tutorial that we have on the content library. So yeah, just a simple animation of a wolf running. And we have some guides that are defined on this wolf. And I've

**[0:41](https://www.youtube.com/watch?v=JUcON39F7zE&t=41)** already done if we dive in here really quickly. I'm just doing a simple setup where I'm smoothing the animation a little bit here. And after that, I'm doing a veum sim of the fur. Then I'm caching that. And um okay, here we have just the body of the wolf. After that, I want three wolves to be running in the snow. So, I'm doing like a couple of uh I'm doing the duplication of the body here. And I'm going to do a couple of versions that we're going to use at different places in the setup.

**[1:15](https://www.youtube.com/watch?v=JUcON39F7zE&t=75)** So, here we have the version of uh this is going to be used as a collider. So we have the body and also the fur that was rasterized as a VDB. And uh this is what we're going to use to render the body of the wolves with this as the velocity computed to have proper motion blur. And we also have the fur here that um yeah maybe I don't need to show that. But yeah, I'm just going to cancel all of that. But this is the fur that we're going to render for the for the final metro render.

**[1:48](https://www.youtube.com/watch?v=JUcON39F7zE&t=108)** Okay. Now the the interesting part. So um we have our wolves that I'm going to load here. Good. And then we can trail their path. So we're going to trail where they are going in space right here. So this can take a little bit of time to cook, but now it it was like pre-cached. And we have all the tra trajectories. So I'm kind of I'm just like baking from like the first 100 frames more or less. And um we see that they have like yeah pretty linear uh trajectory like that.

**[2:19](https://www.youtube.com/watch?v=JUcON39F7zE&t=139)** And if we look at the camera like through the camera that we're going to render with we can see that the the path starts before what the camera is seeing. Like this is the path of the camera and it ends after. So we're just going to try to clip what the camera sees. And this is what's what we're doing here. You can look inside if you want to see how it's being done. But yeah, we're just using the camera first time to clip just the region that we're going to need. And then we bake that into VDB. After that, we dilate this and smooth

**[2:50](https://www.youtube.com/watch?v=JUcON39F7zE&t=170)** just to have like a a rough shape with a little bit of padding of where the walls are going to be. And on this other branch here, we're building building the terrain uh that we're going to instance some snow points in there. So here I'm just like generating a bounding box around the wolves, then setting up the like the thickness of the snow. I'm adding some surface detail here. So it kind of look like some snow patches where the wind have been blowing through and shaping a little bit the the surface.

**[3:23](https://www.youtube.com/watch?v=JUcON39F7zE&t=203)** Converting that to SDF. And finally I'm going to cut out the region that I need to simulate. And then the one thing that we can observe is that if we uh visualize the trail of the wolves, we can see that the the feet like the paws of the wolves are going to go deep in this region here and we still want a little bit of padding here. So that depending on the motion of the wolves, we want like this chunk of snow to be able to uh uh to be pushed in that direction. So we still need some

**[3:53](https://www.youtube.com/watch?v=JUcON39F7zE&t=233)** activated uh dynamic MPM points there, but maybe not at that depth, right? So, what we're going to do next is just look at uh where we uh where like where we are in depth here. And depending on the depth, we're just going to pull this kind of this this uh corner here closer to the wall so that we have less volume to simulate. So, it's easier when uh when you show the results. So basically I'm just like taking the polygon

**[4:26](https://www.youtube.com/watch?v=JUcON39F7zE&t=266)** representation of this patch here and I'm just projecting it to the wolves. And then after that I'm um I'm transitioning. So if if I'm like deeper in the snow, I'm getting closer and closer to where the paws are going in the snow. And as I'm going back to the surface, I'm lurping slowly back to the original position of this snow volume. And this is just going to save us a little bit of volume simulate and will allow us to increase the resolution of

**[4:56](https://www.youtube.com/watch?v=JUcON39F7zE&t=296)** the the point cloud where we need it. So that's it. And here I'm just doing another step of dilation just to make sure that we cover everything that we need. And that is pretty much it. So on this side, if I remove this template. So on this side, we have our static snow that is just going to be a static collider. And on this other side, we have what we're going to fill with npm points. Good. Uh, if we look through the camera and if we look at this static snow, you can see that we are still not covering

**[5:27](https://www.youtube.com/watch?v=JUcON39F7zE&t=327)** everything. So, we're going to need some snow ear and ear. And for that reason, we create this extension that will cover everything that the camera sees. And this old bit here is just to u make sure that we uh basically like extract the we extract the dynamic snow from this. So we create a hole in the middle like you see here and we also convert that to a density VDB and maybe like one thing that is that is

**[5:58](https://www.youtube.com/watch?v=JUcON39F7zE&t=358)** worth mentioning is here we're adding some okay so this is like where we are cutting our dynamic snow from the static snow and here we're just adding a little bit of details because when we are going to rasterize the MTM points to a density grid we're going to get like some bumpiness because it's a little bit uneven. So here I'm also adding this level of fine details to this static mesh so that it blends properly at render time. So when you render the dynamic snow with the static snow, it

**[6:31](https://www.youtube.com/watch?v=JUcON39F7zE&t=391)** should be pretty uh seamless with that. Okay, so all of that was just like prepping of the uh of the asset and the terrain before we get to the actual simulation. But as you're going to see, the rest of the setup is very very straightforward. So, as I said, I'm just going to remove the template here. Okay. So, this is a collider. Uh, here we have our our wolves. If I go back a little bit, here we have our wolves with their fur. Uh, this is going to be a deforming

**[7:03](https://www.youtube.com/watch?v=JUcON39F7zE&t=423)** deforming collider, of course. And this is the setting that we're using for friction and stickiness. We want maybe the snow to stick a little bit to to the paws, but not too much. [snorts] And this is the ceiling that we're using for the static collider. So, we want the snow to really be sticking to it, similar to what you would expect in nature when you have like wet snow falling on other pieces of wet snow. And here we are defining

**[7:35](https://www.youtube.com/watch?v=JUcON39F7zE&t=455)** the dynamic snow. Going to go back to the first frame so we can actually see. And uh here I think I'm just using the snow preset. I'm multiplying the stiffness a tiny bit just to get bigger chunks of snow to all together. And after that I'm just adding some noise the stiffness as I'm usually doing. And here you can see this is like the noise pattern that I'm using. You can use any other noise uh would also work. But this is what I've been using here. And I think yeah I'm remapping this

**[8:08](https://www.youtube.com/watch?v=JUcON39F7zE&t=488)** noise to five and two. And I'm multiplying the stiffness by that just just to add a little bit of variation. And uh that's pretty much it. I don't know. Okay. Yeah. The one thing that is important for this scene since it's going to be mostly passive, we are using this sleeping mechanism. And the only thing that I'm multiplying up here is this velocity threshold. So it it is going to more aggressively deactivate the points and uh be more efficient basically. And when we look at the simulation that

**[8:39](https://www.youtube.com/watch?v=JUcON39F7zE&t=519)** we're getting from this, it looks like that. Okay, so this is our simulation with the wolves that are running through the snow and we have the snow being thrown around like that. And we can visualize this uh state attribute that we've been caching. So you can see like everything that is purple is deactivated. It's passive. And then this uh pink is activated. And we have those boundary points as I mentioned before. And you can, this is

**[9:10](https://www.youtube.com/watch?v=JUcON39F7zE&t=550)** something I haven't mentioned before, but you can even go in the details attribute. And you have this attribute, which is just a string giving you some information about uh the state of your sim. So here you can see that we have like 50% of our particles are active, 44 are passive, and we have a 5% that is boundary particles. So you you could like uh link that to a font sub, a font sub, and just like render it or have it on a flip book. So you have some stats about what's going on in your simulation. You can see like at maybe at

**[9:42](https://www.youtube.com/watch?v=JUcON39F7zE&t=582)** this point it might uh look like we have a lot of active particles because there's a lot of pink. If you look here, we're like 90 almost 98% passive particles. So yeah, it can be like a cool stat to look at. And here, even if you see like a big cut because we're kind of dropping from our static collider, you're not going to see that in camera. So I think the camera stops before we see this. Cool. And yeah, by the way, this could be optimized more like you could just kill the points as they are exiting the camera for drum. So

**[10:13](https://www.youtube.com/watch?v=JUcON39F7zE&t=613)** this is an exercise for you if you want to make the scene even uh more optimized. Okay. And then yeah, the rest is also going to be very straightforward. I don't think I'm doing anything uh fancy from the the rest of the setup. So here we are converting our MPM snow to an SDF. And I think that I'm just going to try to pick a good frame. Okay. Right here. Uh and yeah, the setup that I'm using is very simple. So it's just VDB from

**[10:43](https://www.youtube.com/watch?v=JUcON39F7zE&t=643)** particles. I'm doing some dilation, smooth, and erosion. I'm keeping dilation and erode pretty small because I don't want too much stickiness between the points. I really want to keep this granular look, but uh I still want to get a lot of different frequencies of details, right? So I want some smooth patches like that. I want those very high frequency small details, small bits of snow. And I want also some mid frequency details. So I'm just trying to get this nice distribution here.

**[11:14](https://www.youtube.com/watch?v=JUcON39F7zE&t=674)** And um yeah, this is what we are going to use as our collider because the next step is the debris of course. So now I'm taking my uh MPM simulation the particles here. I'm passing the collider here and we are uh generating our source for our secondary debris simulation. And again this is very like almost the default everywhere. I have multiplied that by five because I was emitting too much based on this JP attribute the

**[11:44](https://www.youtube.com/watch?v=JUcON39F7zE&t=704)** stretching. I also multiplied that by two because there was like according to my taste maybe too much points emitted from slowmoving particles. After that I reduced that from five to three in both of those cases for the point replication and that's it. Everything else is at default. So you get something like that for the particle emission for the source. And then this uh secondary simulation pop network is the same thing that I've been using in all the shots where I'm

**[12:15](https://www.youtube.com/watch?v=JUcON39F7zE&t=735)** doing secondary debris. [snorts] And this is the sim that we get. I think I have visualization here of the the packing. But yeah, we don't really see much because of all of this white coloration. But uh yeah, it gives just another layer of high frequency details to the shot. And when we're done with all of that, we have one branch where we are uh generating our our volume from the DMP particle. And maybe Okay, here it's hard

**[12:46](https://www.youtube.com/watch?v=JUcON39F7zE&t=766)** to see in the viewport. I'm just going to isolate a slice. Okay, if we look at that, we might see a little bit better. Okay. So now we see our snow. So this is density volume that is going to render uh properly for our snow. And then the one thing I want to show you is something I already explained before but I haven't really

**[13:16](https://www.youtube.com/watch?v=JUcON39F7zE&t=796)** showed it here. So you remember this uh toggle mask by surface. So this is we're generating an SDF. Well, in this case it was pre-generated. We're just like object merging it here and connecting it in our second input. But we're grabbing this uh SDF representation and we can use uh we can rasterize the particles to a density grid and then multiply the result by this SDF used as a mask. And this is what we're doing here. And if I disable this and look at the result here, you can see that everything is

**[13:46](https://www.youtube.com/watch?v=JUcON39F7zE&t=826)** just more fuzzy. So it it's hard to distinguish like the general structure of the snow just because everything looks very grainy, very high frequency. And as I'm adding back this back, I'm taking advantage of all of the structure that I've defined in this uh SDF volume. And this is definitely what I want for my snow. I I want something where I can really uh highlight the general structure of the snow. I can see some low, mid, and high frequency details. So, this is what I want. And this is why I'm using this uh toggle here.

**[14:16](https://www.youtube.com/watch?v=JUcON39F7zE&t=856)** I'm just going to kill that to go back to this other view. And uh on this other side, I'm doing the same trick that I showed before. So I'm just taking this uh voxil size from this mpm simulation. I'm copying it here. And here I'm just taking this those secondary points that I will uh also rasterize to density grid with this mpm surface node. And after that I can just merge them together. And uh yeah this multiplier of the

**[14:46](https://www.youtube.com/watch?v=JUcON39F7zE&t=886)** density here this is usually something I will dial in in in the rendering right. So I I will go in lops in my karma uh setup and I will just do some test render and adjust how much I want to multiply those secondary particles such that it gives me the the right kind of details and the right uh uh intensity in the render. So yeah just something that you dial at render time normally. Okay. And after that for the rest here, um, these are just trees that I've been

**[15:19](https://www.youtube.com/watch?v=JUcON39F7zE&t=919)** instancing around on each side of the walls. Really not necessary, but you can use that if you want in your test. And yeah, these are just like trees that I added some snow in the branch. So when you look at the top camera, you have like some details here, some branch with some snow on the on the needles. And yeah, that's pretty much it. If you go to the L network, all of this uh is for the trees. So, you can just delete or disable all of that if you don't want

**[15:49](https://www.youtube.com/watch?v=JUcON39F7zE&t=949)** to mess with that. Same thing for the top network. There's actually a fair bit of things to bake if you want to have snow in the in the trees. So, yeah, all of these can be skipped if you don't want to uh waste some time with that.
