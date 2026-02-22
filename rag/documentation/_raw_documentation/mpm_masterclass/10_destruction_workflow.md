---
title: "MPM Destruction Workflow"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "destruction", "workflow", "fracture", "rbd", "pipeline", "production"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=mQuOe296oeg"
  series: "SideFX MPM H21 Masterclass"
  part: 10
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 246
duration_range: "0:03 - 10:58"
---

# MPM Destruction Workflow

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=mQuOe296oeg)
**Presenter:** Alex Wevinger
**Part:** 10 of 18
**Transcript Lines:** 246

---

## Transcript

**[0:03](https://www.youtube.com/watch?v=mQuOe296oeg&t=3)** So now that we've seen uh each node individually, so the MPM pole structure and the MPM different pieces, let's take a look at uh examples that use both of these nodes together. So here you might recognize our MPM configure middle tearing example scene. And here I've just simulated like the first 10 frames where we have this uh we have this collider going through the middle sheet breaking like that. Perfect. Okay, so now we want to

**[0:33](https://www.youtube.com/watch?v=mQuOe296oeg&t=33)** retarget our middle sheet onto this MPM simulation. So first thing, npm pull structure. So this is our rest model. It's just like a basically just a very thin box with some UVs in this case. And then we pipe our simulation here on the other side. Uh again, I need to switch back to manual mode and set this end frame 10. Good.

**[1:03](https://www.youtube.com/watch?v=mQuOe296oeg&t=63)** So, it seems like it's uh simulating again those 10 frames, but it's not Okay, looking good. And now, okay, we see that the amount of detail is very low. So I'm just going to multiply the And you can see a lot of those elongated

**[1:34](https://www.youtube.com/watch?v=mQuOe296oeg&t=94)** shard pieces that I was talking about. So I'm just going to add Maybe I can disable fracturing and just Something like that should be perfectly fine. Good. And you can see also this maximum distance is working. So we only have

**[2:05](https://www.youtube.com/watch?v=mQuOe296oeg&t=125)** like npm points here. So these fill points are within this range. So there's no fill points added here. So it makes perfect sense. This is exactly what we want. And uh here we can just have a better view at this toggle that I was mentioning before. So if you uh fracture with the points that have this I stretch value, this JP attribute, you're going to get rid of the crack because this is exactly where you want the crack to appear. So for that reason in this case it's really important to check this

**[2:36](https://www.youtube.com/watch?v=mQuOe296oeg&t=156)** align fracture to stretch pieces such that these are not the centrid of your fracture pieces but these pieces that are around the crack are becoming the centroidid. And then if we look at the fracture geometry and we look and we try like to follow uh the edges of those fracture pieces. those are exactly like in between those points and this is where you want the cracks to appear. So then when we do the npm deform pieces

**[3:15](https://www.youtube.com/watch?v=mQuOe296oeg&t=195)** we get something that is not too bad. I'm just going to add some fracture details so it looks even cooler. Okay. So, it's it's uh it's almost good, right? So, we we have something that is not too bad at all, but we have all of those cracks that are not realistic at all. So, if you do metal tearing, you don't expect to see any of these cracks here. Like, it's either torn or not

**[3:47](https://www.youtube.com/watch?v=mQuOe296oeg&t=227)** torn. But metal is not like concrete. It's not going to go halfway like this. So for that we need to use this uh close gap option that I didn't mention before. So if you enable that right away everything is fixed. And so now just to explain a little bit how this is working. So remember when I was talking about this retargeting type I said that it's it's going like per piece right. So it's first deforming the piece per point and then it's looking at at the new size

**[4:18](https://www.youtube.com/watch?v=mQuOe296oeg&t=258)** of the piece after deformation. If the size is too different compared to the the rest size of the piece, then it's going to switch back to this piece transformation. So, what is happening is I'm just going to go back to this drawing board to help understand a little bit. So, uh let's say we have a piece here we have one point here and one point

**[4:50](https://www.youtube.com/watch?v=mQuOe296oeg&t=290)** there. Uh this point is moving in that direction and this point is staying put. So what this means is like after the deformation this point level deformation this piece is going to be elongated like that. Okay. So when the mpm de different pieces sees that it switch back to the piece transformation and then it's going to pick up like maybe a piece that is around here like an npm particle that is around here and it's going to grab the full transformation of this npm particle and apply it to this piece. So the piece will maintain its shape. It's not going

**[5:22](https://www.youtube.com/watch?v=mQuOe296oeg&t=322)** to be stretched like that and uh it's going to stay there. But we have also another piece here. And because the transformation here and the transformation here like the rigid transformation is just slightly well, it's it's a rigid transformation, right? So it's going to introduce a little bit of offset here. So you're going to see like a crack appearing. So this close gap mechanism, what it does is now instead of looking per piece, it's looking per point. So it's looking at

**[5:52](https://www.youtube.com/watch?v=mQuOe296oeg&t=352)** this point and it's comparing. Okay, now I'm switching completely because I was very deformed using the point uh deformation method. Now per point I'm going to compare what would be my position if I were to switch to this uh pointbased deformation instead of going to this uh uh piece base transformation and if the delta is very uh small. So if the difference between going from piece transformation to point deformation is very small I'm going to stick to the

**[6:24](https://www.youtube.com/watch?v=mQuOe296oeg&t=384)** point uh level deformation. So for this point it's going from here to here when we switch between the different method. So this delta is huge. So it's not going to go back to this point deformation. So it's going to stick at this position. But in this case maybe we have a a very small delta, right? So like this would be the position of the point if it's using the point level deformation and this is the position of the point if it's using the piece level deformation. So in this case the delta it's so small that it's going it can in this case snap

**[6:56](https://www.youtube.com/watch?v=mQuOe296oeg&t=416)** back to uh the point level deformation and this will close the gap. So hopefully this is not too uh confusing but uh now if I go back to oudini this is basically what you have here right. So this tolerance is the amount again it's like the same thing as this stretch ratio but instead of being piece level it's now point level. Uh and it acts exactly the same. So more tolerance will uh snap those cracks more aggressively. If you have less tolerance, it's going

**[7:27](https://www.youtube.com/watch?v=mQuOe296oeg&t=447)** to tolerate more uh it's going to allow more cracks to be present. So you just have to play with the slider and get what you need. And in order to avoid to have like a very instantaneous snap between two frames, you have this transition width that as you're increasing this value, it's going to progressively allow the cracks to either uh close or reopen so it doesn't look too weird in animation. So that's it. This is what we get without this option. So definitely a lot of visible

**[7:59](https://www.youtube.com/watch?v=mQuOe296oeg&t=479)** cracks. And when you have this open, it fills pretty much everything. And you're just left with this very nice jagged uh edges of metal tearing. So this is for this example. And now I'm not going to go through too much detail uh in this case, but I just want to show you yet another example and show you just a little trick uh to help you set up this pole structure node without spending too much time. So here I have pre-cached this simulation of this meteorite going

**[8:30](https://www.youtube.com/watch?v=mQuOe296oeg&t=510)** through this building. and uh fracturing the whole building with uh like with this simulation took about 10 minutes. So I don't want to do that live. I'm going to switch to manual mode and put my display flag on this mpm post fracture. So first thing I want to do is to uncheck doing the the fracture itself. And I even want to remove like I don't want to do the interior details. In this case I'm going to visualize the piece that are selected for fracturing.

**[9:01](https://www.youtube.com/watch?v=mQuOe296oeg&t=541)** So if I go back to automatic, you can see that [snorts] like the small pieces like that are being excluded. So this piece is not going to be fracture. Perfect. And then if we go here and we show the fracture points, you can see that we have a ton of points that are being candidate for fracturing. And this is why it's taking so long to actually do it. And uh if you want to fine-tune your fracturing, so if you don't want to be waiting like 10 minutes every single time, single time

**[9:32](https://www.youtube.com/watch?v=mQuOe296oeg&t=572)** that you test some settings, what I would suggest is you can just pick the original asset. So this building and just select a piece like in the 3D connectivity can blast it and then just isolate it. And in this case, of course, it's still like gathering all the points, but the fracturing is only going to take place on this piece. So I can just reenable perform fracture and it's still going to take a little bit of time but yeah in this case it took 5 seconds. I can remove those guides

**[10:06](https://www.youtube.com/watch?v=mQuOe296oeg&t=606)** and now if I just display the wireframe we can see the actual fracturing of the geometry and I can even add back the interior details. So we can really like fine-tune the [snorts] kind of detail that we want So yeah, uh generating the geometry. Yeah, took a little bit more time, but yeah, it's a good way for you to evaluate if you're happy with this kind

**[10:37](https://www.youtube.com/watch?v=mQuOe296oeg&t=637)** of pattern before processing the whole building, which is going to take 10 minutes. Uh and then when we're happy, I can just switch to my cache. And this is the final building all fractured. We have our UVs everywhere. And we can now uh look at a specific frame. So let's say frame 35. And can switch to our different pieces to see this in action.
