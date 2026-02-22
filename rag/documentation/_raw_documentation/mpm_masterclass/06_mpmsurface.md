---
title: "MPM Surface Meshing"
category: _raw_documentation
subcategory: mpm_masterclass
keywords: ["mpm", "mpmsurface", "meshing", "surface_extraction", "post_simulation", "particle_to_mesh"]
agent_relevance:
  Librarian: 0.85
  GraphTracer: 0.70
  VexAuditor: 0.40
source:
  type: youtube_video
  url: "https://www.youtube.com/watch?v=ZNImPE9WbkI"
  series: "SideFX MPM H21 Masterclass"
  part: 6
  total_parts: 18
  presenter: "Alex Wevinger"
transcript_lines: 339
duration_range: "0:01 - 14:02"
---

# MPM Surface Meshing

**Series:** [SideFX MPM H21 Masterclass](https://www.sidefx.com/tutorials/mpm-h21-masterclass/)
**Source:** [YouTube](https://www.youtube.com/watch?v=ZNImPE9WbkI)
**Presenter:** Alex Wevinger
**Part:** 6 of 18
**Transcript Lines:** 339

---

## Transcript

**[0:01](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=1)** Let's now take a look at our new post simulation nodes. So, first up, MPM surface. Okay, so this is very similar to uh I'm just going to put down the node. Okay, so this MPM surface node is very very similar to this other node that we know particle fluid surface. Okay, kind of the same thing. This is more used for flip and this is now used for npm. And if we lay down our npm configure recipe that we know and love.

**[0:33](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=33)** Okay, so we have this simulation of snow falling on this wedge. Now if I just connect that to the MPM surface just like that, you have your sign distance. Like it doesn't look uh pretty or anything, but uh automatically it will like adjust the proper resolution. So it's the proper voxil size and everything for you based on what's uh uh the resolution set in the res in the simulation. So that's one good step and uh right now you can see that we have multiple outputs that you can choose from. So you can just go for a sign

**[1:04](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=64)** distance field uh density VDB or a polygon mesh and here you will have all of your tabs where you control the different settings for each of those outputs. Um so for the surface right now we're using this VD from particle which is the very like basic solution that most people use in general and uh we have also some filtering options that are happening in order right so if I do dilation smooth and erosion it's all happening in sequence like that and we also have this uh mask smooth that I'm

**[1:36](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=96)** going to talk about a little bit later but as you can tell already we have something that is maybe more appropriate for this snow simulation with do by doing a little bit of filtering and the other thing that you can do is not use filtering like that and you can use this new shiny node this neural point surface. So when you use that uh you have like multiple different models to uh pick from. So you have this balance model smooth model which will give rid of get rid of some of the details. this liquid model which is really like

**[2:08](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=128)** optimized for liquid material and this granular uh model again optimized for now granular material like sand soil uh snow this kind of stuff u so doesn't mean that it's always going to be the right solution but just know that we have this new node in H21 this neural point surface uh I gave a talk about this node at craft this year and it's embedded inside of this npm surface and it's also available in the particle fluid surface and uh like very quickly this will just

**[2:41](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=161)** look um at your point cloud a little bit differently. So we take the points we splat them into some kind of density grid with the specific kernel and then we pass this 3D representation of the point cloud through a 3D convolutional neural network to figure out what would be the appropriate sign distance uh information. So like it's a definitely like different way of surfacing point clouds like that. And as I just uh showed, you have like multiple pre-trained model that are coming with this. You can even train your own model if you're interested in doing that. But

**[3:13](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=193)** uh we ship four of them that are like fine-tuned for different types of materials. So okay, enough about that. And now if we go back to those tabs here. So okay, we looked at these. We have the velocity tab. So you can generate a velocity field that goes uh along with your sign distance field. And here by default we are scaling up the voxal size so it doesn't take too much uh place on disk. And we finally have this polygonal mesh output where you can

**[3:44](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=224)** define some adaptivity. If you if you want to save a little bit on on memory, you can increase this and it will like collapse some polygons together as you know. Um and you yeah you can convert that to a poly soup. And here um I'm going to talk a little bit more about that later. But this is where you transfer attribute from let's say the uh MPN simulation. So right now I can just show that to you. If I visualize u this JP attribute so I have some color on my

**[4:15](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=255)** point. I can transfer that onto this mesh right here just by saying from npm particles. Bam. By default it's going to transfer everything here. Here I can be more specific and say okay just transfer the color and this is what we get. Okay so enough with this very basic example. Let's look at uh more interesting stuff. So here we have our Oops. Okay. So I have pre-cached this simulation

**[4:48](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=288)** of the this is this is our by the way all the the tree example I'm going to look at or all configure recipe that comes with Udini. So if you type just mpm configure you have all of these. So the first one is the uh the water glass. After that we have this snow. It's this uh rolling snowball here. And we have this landslide. So these are all coming from the package recipes. And here if we pick like an interesting frame like this one and we drop the MPM

**[5:19](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=319)** surface and connect that. Okay. So we have our blobby uh surface where each particle is just like splat as a sphere. But here I just want you to take a look at this null point surface in liquid mode. And if I convert that to a poly mesh right away you get like a very good-looking surface without much effort at all. And as you can tell if you if you run that on a decent GPU, it's going fairly fast. But yeah, just know that if this uh Onyx inference because this is like internally it's a

**[5:50](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=350)** Onyx model that is being executed. If you're running that on the CPU, this might be uh very expensive. So this neural point approach works really well if you have a good GPU and you have enough memory. But if you're only running on the CPU, you might want to revert to this traditional PDB from particle approach. But yeah, as you can tell, like those smooth and flat regions are very noisefree, very smooth as you expect for liquid and those area where there's more action going on or more sharp and detailed. And this is exactly the advantage of this neural point surface node. It will do like this

**[6:21](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=381)** localized treatment where this area is not treated the same as here because it has a different context in the point cloud. Um, okay. So I think that's that's it for this one. And now if we look at this example, okay, we have our snowball rolling down the slope. Now I want to talk about this uh other filter option. So npm surface connect that here. And now I'm not going to use the point surface. We're just

**[6:51](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=411)** going to go with those filters. And I'm also going to enable this mask smooth. And uh just to show you what it does, take a look at this area here on the snowball. So if I disable it, becomes more noisy. Reenable it becomes more smooth. And here what's happening is we have two settings. So minimum stretch is this JP attribute coming from NTM. So when things are stretching and breaking um this is pretty much setting like a limit to say like everything that is

**[7:22](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=442)** above this number is going to be protected from this smooth. Same thing for curvature. Anything with curvature um higher than this will be predicted. And you can see the mask here. So this is for the stretching attribute and this is for the curvature protecting those edges here. And this shows you that those regions are going to be excluded from the smooth operation but everything else is going to be smoothened. So this can give you more control. Um and then if we switch to this example.

**[8:07](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=487)** here we can use NPS in granular granular mode. So this neural point surface granular and we get something like that. Looks pretty cool. Uh so if we choose the polygon mesh as output we can transfer the color like that. Another thing that we can do is we can use this third input for the rest source model. So if I connect that here and I bring this chunk with the UVs I I can want to

**[8:39](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=519)** like transfer those UVs to my mesh. So I can do that. Here you have as soon as you connect this third input, you get this new tab being populated from rest source model. I can check that. Select the UVs and now I'm transferring the UVs properly to this. And as you can tell, we don't have like those weird interpolation uh issues because each UV island is being transferred individually. And another thing that we can do is I can take this uh static collider. Okay, I'm I'm going to use that as a mask to

**[9:10](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=550)** prune some of the polygons that we don't need. So, I'm just putting that in this uh object merge and I'm plugging that into the last input of this npm surface. Now, again, I have a new tab being populated this VDB surface mask. I can enable that. And now, if we go behind our uh mesh, we can tell that we have introduced some holes here. And this is exactly what we want. like we this is an optimization where we want to prune all the polygons that are not going to be used uh in the render. So if you're

**[9:42](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=582)** rendering with XPU, you want to use your memory as efficiently as possible. And this is definitely something that can help you with that. So uh I'm just going to revert this to zero to show how this works this spread iteration. So first thing that you adjust is this mask offset. So it's basically like pushing the surface up or down to select those polygon for deletion. So just uh just to to show it more clearly, I'm going to exaggerate that by a lot. Okay. So we're removing a lot of polygons. And then I'm

**[10:12](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=612)** going to convert our uh static collider as a polygon mesh so we can see a little bit clearer something that I want to show you. This is going to be a template. And this is our output. And you can see that here we're running into an issue. So we have pruned a lot of polygons but we're now introducing this gap here that we don't want. So this is exactly why you will need this prediteration. So all of those polygons were marked for deletion. But here you can kind of grow or more like

**[10:44](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=644)** reduce this selection of um you can shrink this selection of polygon for deletion in order to get this mesh to meet u this collider here because you don't want to see this gap while you render. So you can increase those spread iteration. So every time you increase this number, it's going to do one iteration of shrinking the deletion mask. And you basically just have to do this until you don't see any gaps anymore. And you get like those two you get this mesh going through the collider exactly like that. And here we can just

**[11:15](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=675)** remove the visualization of the static collider and we can look at it from underneath. And here like if I get this from three to four, you can see that it's uh shrinking this deletion mask. So yeah, just um some small optimization that you can do if you have like a massive amount of geometry that is completely hidden and not being used in your render, you can use these options. And the last thing that we haven't talked about uh is this second input. And um this is going to be a very

**[11:47](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=707)** divisive topic I think but let's take a look at it. So let's say you have this node where you generate the uh sign distance field representation and the velocity field that you're going to use for secondary debris emission. Right? So you want this um to behave like a collider. But for rendering you might want to render a density field. So in this case you would

**[12:18](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=738)** and say okay I want this to be a density field and but for my density field I might want to uh multiply uh sign distance representation of this with the density that I'm I'm rasterizing to a grid and this will give you just a more interesting um uh surface of your snow. So you enable that and it creates this surface tab. So currently I'm creating the surface field. I'm creating the velocity field. I'm creating the density field and I'm multiplying the density

**[12:51](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=771)** field with this surface um field as a mask just to give me more interesting shapes in my snow. But you can see that there's a big duplication of of compute right now because here we are generating the SDF and velocity and we are recreating it from scratch here. So what you can do is pipe this output into this second input. And now if you look at the tab here surface U second input surface. So it's actually using the output of this node. Same thing for the velocity. So there's no duplication of compute. So

**[13:23](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=803)** this might look very odd uh because you're kind of uh putting the output of the MPM surface into the input of the MPM surface. So looks really odd but this is very very common. So very commonly you will want to generate a collider representation of your data and maybe a a render representation of your data. So either it can be a density VDB or it can be a polygon soup. But this happens very often and the fact that you can pull this uh SDF and velocity information and reuse it instead of recomputing it is going to save you a

**[13:57](https://www.youtube.com/watch?v=ZNImPE9WbkI&t=837)** lot of uh farm time for sure. So yeah, I don't know how uh people will appreciate this workflow, but you will see later on when we look at practical scene that
