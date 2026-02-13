---
title: "MPM Post Fracture"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "mpmpostfracture", "fracture", "voronoi", "destruction", "post_simulation"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=XAQgQi3wkNU"
  series: "SideFX MPM H21 Masterclass"
  part: 8
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 240
duration_range: "0:02 - 9:33"
---

# MPM Post Fracture

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=XAQgQi3wkNU)
**Presenter:** Alex Wevinger
**Part:** 8 of 18
**Transcript Lines:** 240

---

## Transcript

**[0:02](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=2)** Okay, let's now take a look at the NTM So, let's lay down our favorite recipe of all time, the MPM configure. So, here we have our snowball falling on this wedge. I'm just going to increase the stiffness by multiplier of five. And we're going to get something just a little more rigid to play with. All good. And uh now let's drop the npm post

**[0:34](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=34)** fracture node. Good. Uh so first input is the geometry that you want to fracture and second Oh and yeah first thing that uh that happens and now I just hit escape is if you look at the very top so I'm going to switch to manual mode. If you switch at the top here of this mpm structure node you have those two parameters. So the start frame it's grayed out because it can be picked up from the data flowing from the npm solver. But the end frame

**[1:05](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=65)** is not defined anywhere. So we have to say ourselves okay I want this simulation to end on frame 50. And the reason why this nodes needs to know when it ends is because when we do destruction with npm is kind of in the the opposite way compared to RBD. So in RBD you would fracture and then you do your simulation. we do our simulation and then we fracture based on where things are dynamically breaking in the MPM sim. So um for example, if I look at at my sim here and I look at frame 50.

**[1:37](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=97)** Okay, so the state of the point cloud here this um and we can also maybe visualize the GP attribute to see where things are breaking. Okay, good. So everything that is red is telling you that this is this has been stretching or fracturing or breaking and everything that is purple as preserved pretty much its its rest volume from the beginning of the simulation. So we can see it more clearly here like when it's fracturing you see that this uh JP attribute is really firing. So it's getting like

**[2:09](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=129)** above one good. So we want to use this information to fracture our original sphere. So if we just look at the output that we get here without doing too much work, we already get something. But now let's look at the parameters to understand a little bit more how this is being fractured. So uh first thing we have this name space. Okay. So this has to be named to properly um to make it work with the npm deform pieces that we're going to use later on. Uh after that the cutting

**[2:39](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=159)** method. So, Boolean can give you those like detailed interior faces. So, we prefer that usually, but you can also use Voroy most of the time. You're going to be fracturing a solid. So, this will stay that way. But you can also fracture a surface. And we have this very cool uh global scale. So, if you have a very good setup working at small scale and you want to port that over to a large scale building, can just multiply that up and everything should transfer properly. Okay. And in order to have this crook very efficiently, we can disable this perform fracture and even uh we're going

**[3:10](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=190)** to remove the display of this geometry. So we can really concentrate on those tabs here with the guides geometry. So this first tab is just to select what pieces you want to use as in fact what pieces you want to be fractured. So if I enable that, this is green. So it means it's going to be a candidate for fracturing. If I increase this minimal uh length, you're going to see at some point the color is going to change. Okay. So now in red it means that this piece is like considered too small with respect to this parameter. So it's not going to be fractured. So this allows

**[3:41](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=221)** you to save a little bit of time. If you have an asset with a lot of balls and small pieces here and there, those are not going to be candidates for fracturing, which is exactly what we want. Good. Uh second thing is this fracture point. Okay. So this is going to take a little bit more explanation. So if I uh display them. So here we see uh all of those points that are candidate for fracturing. And I'm just going for now to disable this align fractures to stretch points. Uh this will need a little bit more explanation. Okay. And

**[4:12](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=252)** this huge distance this is to like dismate the point cloud to not have too many uh pieces. So for now I'm just going to uh remove that completely. So we see all of the candidate that could be used as centroidid for those fracture pieces. Good. So when we play now with this min stretching under this MPM point it will um like if I'm reducing it it will take more points. If I'm increasing it it um it raises the bar for points to be accepted as pieces centroidids. And

**[4:42](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=282)** we can see now that we have just like let's say this plane here of points. It means that uh the material is probably fracturing at that point. And uh we also have those filler points. So sometimes if you only use these points as fracture pieces centrid, it will generate like very elongated shards. Okay? And this will not add this could potentially not add enough resolution for this to for the material to bend. So just in order to have like a a low resolution uniform distribution of fracture, you also have

**[5:13](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=313)** this filler point. And if I'm reducing that, I can start to introduce those filler points in the volume. And this will just add like just a basic resolution everywhere. So things can flex uh a a little bit and you don't have those very long uh elongated shards. Good. This max distance right now it's kind of hard to uh show. Well, I can probably decrease it enough for us to see it, but it's basically like the distance between those filler points and the mpm points. So if you have like a very large asset and it's only being

**[5:44](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=344)** fractured here, it it will not add like filler points here because it will have to be within this distance of the MPM points that are selected. So if I reduce that a lot at some point like some of those points should be disappearing. Yeah. See, so the one that are like too far away from those mpm points are going to be called out. Okay. But let's revert that to the default. Good. Uh, and now we're going to introduce a little bit more of the uh this huge distance. So maybe I can do it

**[6:17](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=377)** I can multiply that by 0.5 and uh we get something that is not too bad. Now I want to talk about this align fracture to stretch point and for that um I'm going to switch to the drawing board. Okay. So let's say you have a material. So this is like a piece of material and you have a fracture happening in the middle right here. So what happens is all of the points that are sitting uh near that fracture those are going to be

**[6:49](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=409)** the candidates for fracturing. But then if you use these to fracture your geometry uh you're going to get something like that. So like this is the center of the the fracture pieces. So you get something like that. And then maybe you have some filler points here. Um, so yeah, you get like big piece here, big piece there, another one here, another one there. But the problem is when this is all going to be moving with the MPM different pieces, you won't recover the crack that you add here because this

**[7:20](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=440)** crack is now filled with solid pieces that won't be able to separate in the middle. So for that reason one thing that you can do is use those point as reference of where the crack is and then the candidate that you want to use for um just going to take another color. The candidate that you want to use for fracturing are actually neighbors to those points. So you pick like let's say the points that are on each side of these. So then when you actually fracture the geometry

**[7:50](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=470)** the the pieces are getting created like that. And now when this is going to separate and move this way and this way, you can recover the crack that goes in between those pieces and it will be aligned on the actual crack of the geometry. And this is exactly what this toggle does. So if you if we look at this plane here, if I enable it, okay, it's it's a little bit tricky to see, but here you

**[8:21](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=501)** can see there's like a tiny void that is being filled when I uncheck that. So these are the actual points aligned with the crack and these are removing the points aligned with the crack and just adding the points that are neighbor to those points. So now the fractures is actually the the the fractured geometry is going to be split exactly where the crack is happening in uh the MPM simulation. So yeah just a little thing to be aware because for metal tearing we're going to see a little bit later. It's very important but for things like concrete it might be

**[8:52](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=532)** less of an issue. So yeah just something to keep in mind. And finally we have our uh cutting geometry that you can visualize. it can sometimes be hard to uh look at like this especially if you add the interior details. It's just even more messy. So in those cases you can just disable that remove all the guides and we can actually like fracture the geometry and take a look. And here I'm just going to add a little bit more details in here so we have something

**[9:30](https://www.youtube.com/watch?v=XAQgQi3wkNU&t=570)** Good. And I can lay down an exploded view. And
