package org.abimon.eternalJukebox.objects

import io.vertx.ext.web.RoutingContext
import org.abimon.eternalJukebox.clientInfo
import kotlin.coroutines.AbstractCoroutineContextElement
import kotlin.coroutines.CoroutineContext

data class CoroutineClientInfo(val userUID: String, val path: String) :
    AbstractCoroutineContextElement(CoroutineClientInfo) {
    constructor(ctx: RoutingContext) : this(ctx.clientInfo.userUID, ctx.normalisedPath())

    public companion object Key : CoroutineContext.Key<CoroutineClientInfo>
}
