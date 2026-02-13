---
title: "MPM Creature Breach"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "creature", "breach", "water", "splash", "character_fx", "ocean"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=Y16j3XTaX-Q"
  series: "SideFX MPM H21 Masterclass"
  part: 15
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 446
duration_range: "0:14 - 17:48"
---

# MPM Creature Breach

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=Y16j3XTaX-Q)
**Presenter:** Alex Wevinger
**Part:** 15 of 18
**Transcript Lines:** 446

---

## Transcript

**[0:14](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=14)** Okay, let's now take a look at this Okay, so this is what we have. This is the full setup. And the first thing that I'm doing here is I'm just like creating this terrain where we're going to have a like a monster going out of the like breaching out from the ground under this kind of a mountain here. And uh you can look at the setup here. But yeah, I'm just like using couple of things. I'm starting from a grid for the the ground

**[0:45](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=45)** and I'm going to add some noise to it just for the the terrain itself. And then I'm grabbing some assets here. Like I have this montane asset that I'm going to cap and use for the uh the point where our our creature is going to breach out from. And I'm also grabbing some rock assets that I'm going to scatter on the terrain. And when we're I should probably just look at the cache. It's going to be faster. So when we're done here, we have something like that. And our camera is going to be

**[1:17](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=77)** placed pretty much here. And we have our monster like breaching out of there. After that here we have our main character. So if I dive in in here so we have our animation coming as an Olympic. So basically have this this guy that is called brute and it's now packaged with the H21. So maybe you know about this uh character already. But yeah we basically have this animation that was prepared by one of my colleague and he's just

**[1:47](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=107)** getting up like that. And we don't really want to use this part of the animation where is like in this fighting pose. We just want to use the the part where it's coming from uh under the ground and then up like pretty much like that and we will be done. So uh this is our animation. This is the low resolution version of the asset. So here I'm just doing a this is not like the proper way to do this in production but

**[2:19](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=139)** So just a moment for it to load. Okay. So here we have our IRS asset and this has the the UV. This has everything for the lookdev to be appi applied properly. So give it a moment to load again. Maybe I should not have checked this. But yep. Okay. So yeah, don't know why it's so

**[2:50](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=170)** slow because it's not that many. Like it's half a million points. I don't know why it's that slow in the viewport, but whatever. And we're basically just retargeting our animation on that. And the only part I want to highlight is this this enforce max velocity. So if I dive in there, the only thing that I'm doing and I can probably I pick a frame where we see something happening with this. So maybe Okay. So see how fast see how fast it's moving his feet like that. So if I pick like the frame like this and I compare what I had before. So this is before we're going through this

**[3:23](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=203)** solver and this is after. You can see that after I'm I'm just pulling the toes and some part of the feet a little bit back here. And this is because I'm enforcing a maximum amount of displacement between each frame. And this will prevent uh the material from flying over in all direction when there's something that is moving just a little bit too fast in the animation. So inside here just a wrangle where I'm just checking okay between the current frame and the previous frame which is the delta what is like the the difference in displacement in space. And then I'm going to say okay I never want

**[3:55](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=235)** this displacement to exceed uh distance of 025. So when this is bigger, we're just grabbing this uh 0 255 as the maximum uh value and then we multiply that by the direction of this displacement. So we will like frame by frame enforce this maximum displacement and it will avoid a lot of problem in the end in terms of having the material blowing up in all direction. So this is the only important part that we're doing after that is just a point deform of this iris asset and we are good.

**[4:26](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=266)** Okay. uh here uh we're grabbing this animation and we are building a mask based on it. So in this subn network we're just going to grab this is exactly the same thing that we've done for the wolf scene. So we're just grabbing couple of frames throughout the frame range and we're building this mask representing where the character is going to be and we're going to use that as a stencil to uh remove well to isolate a part of the terrain to be dynamic. So here, this is what we have. And if I dive inside real quick, so we have our motion trail,

**[4:59](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=299)** the character going up like that. And uh then we're building our mask as a SDF. And then I'm I'm just like carving a part of the terrain where this is all going to be simulated with npm. And this is all going to be just a static collider. And that's it. So this is our first npm simulation. There is nothing fancy going on. So this is our terrain as I said. Then if we go to the first frame, I'm just using that as a source. Uh I think here I'm just playing with the stiffness a little bit and I'm

**[5:29](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=329)** starting from the soil preset. Yeah, that's it. Soil preset, multiplying the stiffness by 160. And here I'm just adding some noise. Uh well, I'm visualizing currently the noise as the color, but it's just generating a noise and then multiplying the stiffness with it just to add a little bit of variation. But then if you look at that like maybe I can hide that. So if we look at those points this is super coarse right? So this is not going to work very well if you want this to be like a realistic scene uh that is

**[6:01](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=361)** realistic scene of some rocks and so like breaking from a collider going through it. But we have some solution uh later in the setup. So this is our initial simulation just to have a rough first view of how this soil should be breaking from this collider. So if we just look at the sim uh we're not seeing the collider currently but if I visualize it like that. Okay we have brute coming out of the ground like this breaking the ground which is great. And then um just to make sure that I'm not

**[6:32](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=392)** skipping over any details here. Yeah, I'm just adding some stickiness because I want some soil to be like sticking to the arm like that. This is exactly kind of detail I'm looking for. And for the static ground, same thing. A little bit of stickiness. That's it. This is static. And this guy is animated deforming. And as I said before in the presentation, those animated deforming collider are now much more reliable. And this is going to be this is going to be playing a very important part in this whole setup. Okay. Then when I'm done with with that, I'm doing something

**[7:02](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=422)** special here. Oh yeah, maybe just to make sure. Yeah, nothing special happening here. So yeah, the default all of the those parameters on the solver are using the default. So nothing going on here. And here I'm just like setting some stuff not to output all of the attributes for no reason. Okay. And then here I'm going to um gather what is the maximum GP attribute throughout this whole simulation. What is our uh maximum stretching or fracturing or breaking that we're going to uh reach? And then

**[7:34](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=454)** we can visualize that a little bit JP. And then if we look at what we have and I'm just going to remove brute here. Okay, we see everywhere that the material is going to break. So you can tell that everything that is blue is going to uh stay as a whole piece, right? Like this is never going to fracture throughout the whole simulation. So we have a lot of points like this is filled with information filled with points that are never going to be used because there's no fracture happening. So the trick here is to use this low res simulation that will be

**[8:06](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=486)** we'll be going through pretty quickly to detect exactly where we need the resolution. And then what we can do is we can blast. So here uh just going to go back in the auto update mode. And here we can blast. Yeah, it's better if I go back to the first frame. We blast all of the points that are going to be fracturing or that are going to exhibit some kind of detail and some kind of resolution. Okay, but we keep everything that is staying old and that is not fracturing.

**[8:36](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=516)** And here comes the trick. So we just convert that to a collider. And now we can see much better uh what I was trying to show in the viewport as point. But you can see like everywhere that things are breaking we are removing that but we're keeping everything that is staying as a whole piece. Then we do another npm simulation but at a higher resolution. So if you look here we're we're simulating pretty much at 11. Okay. And here we're we're going to do another simulation but 06, right? So

**[9:07](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=547)** almost half of the resolution. So in 3D it's like almost eight times as many particles. So it's a big jump in resolution. But now what we do is we gather all of our collider ears and we merge them together. And then we take this dynamic patch of land that we're going to extract this um those colliders. And then we're left with this result that might take a little bit of time to cook. Nope, that was pretty quick. And yeah, now we're left with everything that is going to be

**[9:39](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=579)** fracturing in the sim. So we are really like concentrating this resolution exactly where it matters. And then we use that as a source. So we turn that into a source with a higher resolution. And this is what we get. And think about that like at the moment it's like okay 16 million points. But if you would fill this whole volume uh without this optimization with this amount of resolution, you would probably not be able to sim that on a regular GPU,

**[10:10](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=610)** right? Um and then in this case we are using the low resolution sim as a collider here as an animated deforming. So uh this low resolution is going to guide this low resolution collider is going to guide the high resolution MPM simulation. And in this case we are cranking both friction and stickiness to absolute like a very very high value because we want if I have like a new mpm point at high resolution that is touching this I really want this to feel um as it is fully connected to this piece. So that's why I'm cranking those

**[10:42](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=642)** parameter that high. I never want like those pieces to be completely exposed. So we so we kind of want to to to um hide the fact that this is lower lower resolution than this higher resolution sim. So if we have a lot of high resolution point sticking to this low resolution piece, this is going to do exactly what we want. And then we do another sim and this is pretty much again the default. And this is what we're going to get in the end. So we have this cool simulation of the the

**[11:13](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=673)** groundbreaking and this is much higher res. As you can see, you have a lot more details and we're currently visualizing this JP attribute and this is all looking good. But we want more details because even even what at that level of uh detail, it's still not going to work uh perfectly well. Like if you if you would render those points as individual like grain of uh sand or whatever, uh it would still read to Lorz. So one of the tricks that we do um is okay, so this part are the

**[11:44](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=704)** secondaries. I'm going to go back to this. But in terms of the the core uh the core ground that we're going to render, this is where the magic is happening. So here we have brute. Here we have our uh terrain. This is the low resolution MPM sim again. So our primary sim. So we're just going to wait for this to cook a little bit. And here in terms of the filtering, I'm just okay. I'm doing like one dilation, one smooth, and then

**[12:14](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=734)** four erosion. So I'm going like inside of the surface to make sure that there is some padding over this low resolution surface. And on this side here I'm again yet again taking this um dynamic ground and filling with some points. But here I'm fill that I'm filling that ground with even more resolution. So when this is done cooking I'm just going to show Okay. So we have here 166 million points

**[12:47](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=767)** and the resolution is 04. So even higher resolution than what we had in our latest MPM sim. And here we're just pruning everything that is not going to be seen. So we just want this narrow band of particles to be sitting on top of the pieces that are going to uh be seen. So we want to cover the cracks and we want to cover the exterior surface that is not going to be destroyed. So we can keep we can remove a lot of the points that we don't need and we don't see in the render. So we're down to half

**[13:17](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=797)** of the amount of points. 88 million. And then we can catch that. Okay, we set the B scale and okay. So remember we're always doing those uh recording at half res. So this is still not like the final res that you see in the in the shot that I showed at the beginning. But this would be if you double this amount of resolution uh and you set this global scale like this global scale attribute here you put that back to one then you're really going to see like the final resolution and from my uh test

**[13:47](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=827)** this would account like if this whole volume would be filled with that resolution it would be like around 1 billion points for the whole shape. So this is getting pretty irres. And then we store this rest attribute that we're going to use for shading. And those um two nodes are doing something fairly uh basic but really interesting in this case. So we are just based on this first frame of both our simulations. So here we have our lowres npm, high res npm. We're just uh combining them here. And

**[14:18](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=858)** then we're going to capture uh what is the closest npm point to me. So we just store that here. And here I'm just adding a little bit of noise such that it doesn't look like a perfect vinary diagram. So it's not exactly picking the closest point. There's just a little bit of variation that I'm adding here to make it look more uh interesting when it's breaking. And after that we are just moving those pieces. So you remember on each of those points we have an orient attribute that is coming out of the solver of the MPM solver. So here we can just say okay grab the uh so we

**[14:50](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=890)** have this rest that is coming from our simulation here at the first frame. So we put everything back into uh this rest position at the origin and then we have our orient attribute here that we convert into a 3x3 matrix and then we multiply uh this point at rest with this 3x3 matrix to have the correct orientation of this block of points and then we put it back into this uh anim space that is coming from this branch here. So like very little amount of code

**[15:20](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=920)** but it's doing exactly what we want. So if we look at the result that we get here, so we are basically like retargeting this dynamic motion onto this very high resolution point cloud. And as as I was saying like if you zoom on it on on this part here and you go inside, you can see that the interior is completely empty. And this is exactly what we want. We don't want to pay for the cost of uh this old volume being being filled with point because we're never going to see that at render time. And after that, just a matter of computing the velocity on that and we're good to render this as points and it

**[15:50](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=950)** should work pretty good. And for the secondaries, I'm just taking this low res MPM. No, I think yeah, this is the low res MPM respining everything together. So if I just view this cached version. Okay, so we have everything as a collider. So the two mpm sim combine together and then we use that as a collider for our secondaries. For the secondaries, the only thing that I'm doing if I just view this mpm debris

**[16:21](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=981)** source. Okay, I'm also grabbing this rest attribute as this is being used uh for the shading. And then I'm just animating those two. So this minimum stretch, so minimum JP and minimum speed. I'm just animating those such that at the beginning I have more debris emission. But at the end when everything is crumbling, I don't want to uh I don't want to crash the simulation or go to a like horrible amount of of points. So I'm just trying to keep that reasonable. So I'm ramping this limit of what is like the minimum stretching that will trigger a point emission. I'm increasing

**[16:53](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=1013)** that to rem to reduce the amount of point that is being emitted. And I'm doing the same thing for this minimum speed. And in the end I have this kind of point cloud for the the emission. And uh this network is exactly the same thing that I've been doing for all of the other uh scenes. So just I'm computing the the point density. So the amount of clump of points like how many neighbors are around a single point. So I'm just computing that as a density attribute. And I'm going to drive this wind and air resistance based on that.

**[17:24](https://www.youtube.com/watch?v=Y16j3XTaX-Q&t=1044)** And after that I'm handling the collisions right here. Um, and then you get, if I go back to manual mode, uh, to automatic mode, and we look at what we have, we get some cool secondary path of debris flowing on our character here. And this is for the secondaries. This concludes this whole uh, creature breach setup.
